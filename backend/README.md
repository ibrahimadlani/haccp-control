# HACCP Control — Backend

**FastAPI · PostgreSQL 16 · Python 3.12 · SQLAlchemy async · Docker · MinIO · Prometheus**

API REST multi-tenant pour la traçabilité sanitaire en restauration (norme HACCP France) — relevés de température, non-conformités, actions correctives, pointages RH.

---

## Table des matières

1. [Démarrage rapide](#1-démarrage-rapide)
2. [Architecture](#2-architecture)
3. [Authentification](#3-authentification)
4. [Référence API](#4-référence-api)
   - 4.1 [Sessions et authentification](#41-sessions-et-authentification)
   - 4.2 [HACCP — Relevés de température](#42-haccp--relevés-de-température)
   - 4.3 [Non-conformités](#43-non-conformités)
   - 4.4 [Équipements](#44-équipements)
    - 4.5 [Catalogue — Fournisseurs et produits](#45-catalogue--fournisseurs-et-produits)
    - 4.6 [Réceptions — Sessions de livraison](#46-réceptions--sessions-de-livraison)
    - 4.7 [Nettoyage — Routines et logs](#47-nettoyage--routines-et-logs)
    - 4.8 [Utilisateurs et rôles](#48-utilisateurs-et-rôles)
    - 4.9 [Organisation et administration](#49-organisation-et-administration)
    - 4.10 [Time clock — Pointage RH](#410-time-clock--pointage-rh)
    - 4.11 [Système](#411-système)
5. [Modèle de données](#5-modèle-de-données)
6. [Schémas de requête / réponse](#6-schémas-de-requête--réponse)
7. [Variables d'environnement](#7-variables-denvironnement)
    - 7.1 [Feature flags et limites de plan](#71-feature-flags-et-limites-de-plan)
8. [Migrations Alembic](#8-migrations-alembic)
9. [Observabilité](#9-observabilité)
10. [Routes dépréciées](#10-routes-dépréciées)
11. [Stockage S3 / MinIO](#11-stockage-s3--minio)
12. [Conventions de développement](#12-conventions-de-développement)
13. [CI/CD](#13-cicd)

---

## 1. Démarrage rapide

### Prérequis

- Docker ≥ 24 et Docker Compose V2
- Aucune dépendance Python locale — tout tourne dans les conteneurs

### Lancement

```bash
# Depuis la racine du dépôt
docker compose up --build
```

### Services exposés

| Service | URL locale | Identifiants | Usage |
|---------|-----------|-------------|-------|
| **API FastAPI** | `http://localhost:8001` | — | Endpoint principal |
| **Swagger UI** | `http://localhost:8001/docs` | — | Exploration interactive |
| **ReDoc** | `http://localhost:8001/redoc` | — | Documentation lisible |
| **PostgreSQL** | `localhost:5433` | `haccp_user` / `haccp_password` | Accès direct BD |
| **MinIO Console** | `http://localhost:9001` | `minioadmin` / `minioadmin` | Interface S3 |
| **Prometheus** | `http://localhost:9090` | — | Métriques brutes |
| **Grafana** | `http://localhost:3001` | `admin` / `admin` | Dashboards |

Pour changer les ports en cas de conflit :

```bash
API_PORT=8010 POSTGRES_PORT=5434 GRAFANA_PORT=3002 docker compose up --build
```

### Commandes essentielles

```bash
# Appliquer toutes les migrations en attente
docker exec haccp_api uv run alembic upgrade head

# Générer une nouvelle migration depuis les modèles
docker exec haccp_api uv run alembic revision --autogenerate -m "description"

# Rollback d'une migration
docker exec haccp_api uv run alembic downgrade -1

# Voir l'état des migrations
docker exec haccp_api uv run alembic current

# Lancer les tests
docker compose exec api uv run pytest
```

---

## 2. Architecture

### Couches applicatives

```
┌──────────────────────────────────────────────────────────────┐
│  API Layer  app/api/router.py                                 │
│  Assemblage des routeurs modules sous /api/v1                │
│  auth · tenant · personnel · catalog · equipments            │
│  receptions · haccp · cleaning · nonconformities             │
├──────────────────────────────────────────────────────────────┤
│  Domain Layer  app/modules/*                                   │
│  router.py · service.py · schemas.py · models.py             │
│  Logique métier async, validations et mapping ORM/Pydantic    │
├──────────────────────────────────────────────────────────────┤
│  Core Layer  app/core/                                         │
│  config · database · security · dependencies · monitoring     │
│  feature_flags · features · role_utils · time_utils           │
├──────────────────────────────────────────────────────────────┤
│  Model Layer  app/models/                                     │
│  SQLAlchemy ORM async · TimestampMixin (created_at/updated_at)│
├──────────────────────────────────────────────────────────────┤
│  PostgreSQL 16  (asyncpg)                                     │
└──────────────────────────────────────────────────────────────┘
```

### Multi-tenancy

Le modèle de séparation des données est **row-level tenancy** : chaque ligne des tables opérationnelles porte un `organisation_id` et/ou un `etablissement_id`. Il n'y a pas de schéma PostgreSQL séparé par client. Toutes les requêtes filtrent systématiquement sur ces deux colonnes via les dépendances `CurrentSite` et `CurrentOrg`.

### Structure du dossier `app/`

```
app/
├── main.py                        # App FastAPI + CORS + monitoring + /health
├── api/
│   ├── deps.py                    # Aliases de dépendances réutilisables
│   └── router.py                  # Agrégateur des routeurs modules sous /api/v1
├── core/
│   ├── config.py                  # Settings Pydantic depuis .env
│   ├── database.py                # AsyncSession factory (get_db)
│   ├── security.py                # JWT encode/decode, bcrypt
│   ├── dependencies.py            # Middleware auth (get_current_establishment…)
│   ├── feature_flags.py           # Guard require_feature(Feature.*)
│   ├── features.py                # Enum des fonctionnalités activables
│   ├── role_utils.py              # is_manager_role(), is_platform_admin_role()
│   ├── time_utils.py              # now_for_site(timezone) — timestamps site-aware
│   ├── monitoring.py              # Sentry + Prometheus setup
│   └── deprecation.py             # Mapping routes legacy → REST v1
├── models/
│   ├── base.py                    # Base ORM + TimestampMixin
│   └── __init__.py                # Ré-export des modèles globaux
└── modules/
    ├── auth/                      # Sessions organisation/établissement + opérateur PIN
    ├── tenant/                    # Organisations, établissements, settings, plan limits
    ├── personnel/                 # Users, operators, roles
    ├── catalog/                   # Suppliers et products
    ├── receptions/                # Sessions de réception + lignes de livraison
    ├── equipments/                # Équipements HACCP
    ├── haccp/                     # Relevés de température + time clock status/events
    ├── cleaning/                  # Zones, routines, tâches, logs
    └── nonconformities/           # Workflow OPEN→IN_PROGRESS→RESOLVED→CLOSED
```

Le routeur principal inclut les modules dans cet ordre via `app/api/router.py` :
`auth`, `tenant`, `personnel`, `catalog`, `equipments`, `receptions`, `haccp`, `cleaning`, `nonconformities`.

---

## 3. Authentification

L'API implémente **4 mécanismes d'authentification distincts** adaptés aux différents contextes d'usage.

### 3.1 Establishment JWT — Device binding (tablette partagée)

Le mécanisme principal. Une tablette partagée est verrouillée à **un seul établissement** via un JWT signé.

**Obtention :**
```http
POST /api/v1/establishment-sessions
Content-Type: application/json

{
  "email": "manager@restaurant.fr",
  "password": "MonMotDePasse1!",
  "etablissement_id": "22222222-2222-4222-8222-222222222222"
}
```

**Utilisation :**
```http
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

**Contenu du JWT :** `organisation_id`, `etablissement_id`, `utilisateur_id` (manager), `token_use="establishment_access"`, `exp`.

**Durée :** `ESTABLISHMENT_ACCESS_TOKEN_EXPIRE_HOURS` (12h par défaut, configurable 1-24h).

**Contexte injecté :** dépendance `CurrentSite` → objet `CurrentEstablishment` avec `organisation_id`, `etablissement_id`, `nom_site`, `timezone`, `manager_user_id`.

**Erreurs :** `401` token invalide ou expiré, `401` si l'établissement a été supprimé depuis l'émission du token.

---

### 3.2 Operator PIN — Dual auth tablette

Après le device binding, chaque opérateur s'authentifie avec son **PIN à 4 chiffres** via deux headers HTTP supplémentaires. Ce mécanisme se **cumule** avec le JWT d'établissement.

**Headers requis :**
```http
Authorization: Bearer <establishment_jwt>
X-Device-Pin: 1234
X-Operator-Id: 4b51ad67-4805-43e9-91a3-2fc60f930636
```

**Validation :** l'opérateur doit avoir une affectation active sur l'établissement du token ET son PIN doit correspondre au hash bcrypt stocké AND son rôle ne doit pas être manager (les managers ne s'authentifient pas par PIN).

**Contexte injecté :** dépendance `CurrentOperator` → objet `Utilisateur` complet.

**Erreurs :** `401 "Invalid operator credentials."` (message générique intentionnel pour éviter l'énumération).

---

### 3.3 Organisation JWT — Supervision multi-sites

Pour les admins organisation qui gèrent plusieurs établissements depuis un portail de supervision.

**Obtention :**
```http
POST /api/v1/organisation-sessions
Content-Type: application/json

{
  "email": "admin@groupe-restauration.fr",
  "password": "MonMotDePasse1!"
}
```

**Contenu du JWT :** `organisation_id` seulement, `token_use="organisation_access"`.

**Contexte injecté :** dépendance `CurrentOrg` → objet `CurrentOrganisation` avec `organisation_id`, `nom_entite`.

---

### 3.4 Platform Admin Key — Opérations réservées plateforme

Pour les opérations destructives ou irréversibles au niveau SaaS (création de tenant, hard-delete).

**Header requis :**
```http
X-Platform-Admin-Key: <valeur de PLATFORM_ADMIN_KEY dans .env>
```

**Dépendance :** `require_platform_admin_key` — lève `401` si absent ou incorrect.

> ⚠️ **Production :** cette clé doit être un secret aléatoire d'au moins 32 caractères, différente de `JWT_SECRET_KEY`.

---

### Tableau récapitulatif

| Dépendance FastAPI | Headers requis | Contexte retourné | Endpoints |
|-------------------|---------------|------------------|-----------|
| `CurrentSite` | `Authorization: Bearer <establishment_jwt>` | `CurrentEstablishment` | Majorité des endpoints tablette |
| `CurrentOperator` | Bearer + `X-Device-Pin` + `X-Operator-Id` | `Utilisateur` | Relevés, pointages, acknowledge, action corrective |
| `CurrentOrg` | `Authorization: Bearer <organisation_jwt>` | `CurrentOrganisation` | Supervision organisation |
| `require_platform_admin_key` | `X-Platform-Admin-Key` | — (garde) | `POST /organisations` |

---

## 4. Référence API

**Préfixe global :** `/api/v1`

---

### 4.1 Sessions et authentification

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `POST` | `/establishment-sessions` | Aucune | Login manager — crée le JWT d'établissement (device binding) |
| `POST` | `/organisation-sessions` | Aucune | Login admin organisation — crée le JWT de supervision |
| `GET` | `/establishments/{etablissement_id}` | Aucune | Métadonnées publiques d'un établissement (page de login tablette) |
| `POST` | `/operator-sessions` | `CurrentSite` + PIN headers | Valide l'identité opérateur (dual auth) |
| `GET` | `/establishments/{etablissement_id}/users` | `CurrentSite` | Liste les opérateurs du site. Filtre optionnel `?role=SITE_EMPLOYEE` |

**`POST /establishment-sessions`**

```json
// Requête
{
  "email": "manager@restaurant.fr",
  "password": "MonMotDePasse1!",
  "etablissement_id": "22222222-2222-4222-8222-222222222222"
}

// Réponse 200
{
  "access_token": "eyJhbGci...",
  "token_type": "bearer",
  "establishment": {
    "organisation_id": "11111111-1111-4111-8111-111111111111",
    "etablissement_id": "22222222-2222-4222-8222-222222222222",
    "nom_site": "Restaurant Le Provençal",
    "timezone": "Europe/Paris"
  }
}
```

Codes : `200` succès · `401` identifiants incorrects · `404` établissement introuvable · `401` manager sans rôle manager sur ce site.

**`GET /establishments/{etablissement_id}`**

```json
// Réponse 200
{
  "etablissement_id": "22222222-2222-4222-8222-222222222222",
  "nom_site": "Restaurant Le Provençal",
  "timezone": "Europe/Paris"
}
```

> Note : ce endpoint accepte un UUID. Les valeurs non-UUID retournent `422`.

---

### 4.2 HACCP — Relevés de température

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `POST` | `/temperature-records` | `CurrentSite` + `CurrentOperator` | Enregistre un relevé. **Ouvre automatiquement une NonConformity si non-conforme.** |

**`POST /temperature-records`**

```json
// Requête
{
  "equipment_id": "33333333-3333-4333-8333-333333333333",
  "measured_value": "14.50",
  "source": "MANUEL",
  "measured_at": "2026-06-03T09:30:00+02:00"
}
```

- `measured_value` : format `-?\d{1,3}(?:\.\d{1,2})?` — max 3 chiffres entiers, max 2 décimales.
- `source` : `MANUEL` ou `IOT`.
- `measured_at` : ISO 8601 avec timezone. Si absent, utilise `now()` converti au fuseau de l'établissement.

```json
// Réponse 201 — relevé conforme
{
  "id": "aaaa0001-...",
  "etablissement_id": "22222222-...",
  "equipment_id": "33333333-...",
  "utilisateur_id": "4b51ad67-...",
  "measured_value": "14.50",
  "temperature_min_cible": "0.00",
  "temperature_max_cible": "4.00",
  "is_conforme": false,
  "action_corrective_required": true,
  "nonconformity_id": "cccc0001-...",
  "source": "MANUEL",
  "measured_at": "2026-06-03T09:30:00+02:00"
}
```

Quand `is_conforme: false`, le champ `nonconformity_id` contient l'UUID du ticket automatiquement ouvert. Ce ticket est en status `OPEN` et doit être traité via les endpoints de non-conformité.

Codes : `201` succès · `404` équipement introuvable · `401` PIN ou opérateur invalide.

---

### 4.3 Non-conformités

**Machine d'état :**

```
     [relevé hors plage → création automatique]
                     │
                     ▼
                   OPEN
                     │
        (opérateur PATCH /acknowledge)
                     │
                     ▼
               IN_PROGRESS
                     │
        (opérateur POST /corrective-action)
                     │
                     ▼
                 RESOLVED
                     │
          (manager PATCH /close)
                     │
                     ▼
                  CLOSED
```

| Méthode | Path | Auth | Description | Transition |
|---------|------|------|-------------|-----------|
| `GET` | `/nonconformities` | `CurrentSite` | Liste paginée avec filtres | — |
| `GET` | `/nonconformities/stats` | `CurrentSite` | Compteurs par statut + dernière ouverture | — |
| `PATCH` | `/nonconformities/{id}/acknowledge` | `CurrentSite` + `CurrentOperator` | Opérateur prend en charge | `OPEN → IN_PROGRESS` |
| `POST` | `/nonconformities/{id}/corrective-action` | `CurrentSite` + `CurrentOperator` | Opérateur signe + photo optionnelle | `IN_PROGRESS → RESOLVED` |
| `PATCH` | `/nonconformities/{id}/close` | `CurrentSite` (manager) | Manager clôture définitivement | `RESOLVED → CLOSED` |

**`GET /nonconformities`**

Query params :
- `status` : `OPEN` | `IN_PROGRESS` | `RESOLVED` | `CLOSED` (optionnel — tous si absent)
- `type` : `TEMPERATURE` (optionnel)
- `limit` : entier 1-500, défaut `100`

```json
// Réponse 200
{
  "items": [
    {
      "id": "cccc0001-...",
      "workflow_type": "TEMPERATURE",
      "status": "OPEN",
      "opened_by_name": "Jean Dupont",
      "opened_at": "2026-06-03T09:30:00+02:00",
      "assigned_to_name": null,
      "assigned_at": null,
      "resolved_at": null,
      "closed_by_name": null,
      "closed_at": null,
      "closing_comment": null,
      "source_record_id": "aaaa0001-...",
      "equipment_id": "33333333-...",
      "equipment_name": "Chambre froide positive 1",
      "measured_value": "14.50",
      "temperature_min": "0.00",
      "temperature_max": "4.00",
      "deviation_celsius": "10.50",
      "source": "MANUEL",
      "corrective_action_id": null,
      "corrective_action_description": null,
      "corrective_action_signed_at": null,
      "corrective_action_photo_url": null
    }
  ],
  "total_open": 3,
  "total_in_progress": 1,
  "total_resolved": 12,
  "total_closed": 45
}
```

> Les compteurs `total_*` sont calculés sur **l'ensemble des non-conformités** de l'établissement, pas seulement la page courante.

**`PATCH /nonconformities/{id}/acknowledge`**

Aucun body. Requiert le JWT d'établissement **ET** les headers PIN opérateur.

Modifie : `status = IN_PROGRESS`, `assigned_to_id = operator.id`, `assigned_at = now()`.

Codes : `200` succès · `404` ticket introuvable · `409` si statut ≠ `OPEN`.

**`POST /nonconformities/{id}/corrective-action`**

Body multipart/form-data :
- `description` (champ texte, 3-5000 caractères, **obligatoire**)
- `photo` (fichier image, optionnel — `.jpg`, `.jpeg`, `.png` uniquement)

```json
// Réponse 201
{
  "id": "dddd0001-...",
  "releve_id": "aaaa0001-...",
  "utilisateur_id": "4b51ad67-...",
  "description": "Produits isolés, maintenance chambre froide prévenue, température vérifiée à 3.8°C à 14h30.",
  "photo_s3_key": "haccp/22222222-.../corrective-actions/uuid.jpg",
  "photo_url": "http://localhost:9000/haccp-documents/haccp/22222222-.../corrective-actions/uuid.jpg",
  "signee_at": "2026-06-03T10:15:00+02:00"
}
```

Modifie sur la NonConformity : `status = RESOLVED`, `resolved_at = now()`.

Codes : `201` succès · `409` si statut ≠ `IN_PROGRESS` · `409` si une action corrective existe déjà · `422` description vide.

**`PATCH /nonconformities/{id}/close`**

```json
// Requête (body optionnel)
{
  "closing_comment": "Vérification réalisée, conforme aux exigences du PMS."
}
```

Modifie : `status = CLOSED`, `closed_by_id = manager_user_id`, `closed_at = now()`, `closing_comment`.

Codes : `200` succès · `409` si statut ≠ `RESOLVED`.

---

### 4.4 Équipements

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `GET` | `/equipments` | `CurrentSite` (+ PIN optionnel) | Liste les équipements actifs de l'établissement |
| `POST` | `/equipments` | `CurrentSite` | Crée un équipement HACCP |
| `PATCH` | `/equipments/{id}` | `CurrentSite` | Met à jour un équipement |
| `DELETE` | `/equipments/{id}` | `CurrentSite` | Soft-delete (ou hard avec `?hard_delete=true`) |
| `GET` | `/establishments/{etablissement_id}/equipments` | `CurrentSite` | Liste les équipements d'un établissement spécifique (scope org) |
| `POST` | `/establishments/{etablissement_id}/equipments` | `CurrentSite` | Crée un équipement pour un établissement spécifique |

**Types d'équipements (`TypeEquipement`) :**

| Valeur | Description |
|--------|-------------|
| `CHAMBRE_FROIDE_POSITIVE` | Chambre froide positive |
| `CHAMBRE_FROIDE_NEGATIVE` | Chambre froide négative / surgélateur |
| `REFRIGERATEUR_VIANDE` | Réfrigérateur viande |
| `REFRIGERATEUR_POISSON` | Réfrigérateur poisson |
| `VITRINE_REFRIGEREE` | Vitrine réfrigérée |
| `VITRINE_CHAUFFANTE` | Vitrine chauffante |
| `CELLULE_REFROIDISSEMENT` | Cellule de refroidissement rapide |
| `CHAUFFE_ASSIETTE_FOUR` | Chauffe-assiette / four |
| `CONGELATEUR_CONSERVATEUR` | Congélateur conservateur |
| `RESERVE_SECHE` | Réserve sèche |
| `AUTRE` | Autre (défaut) |

**Validations températures :**
- Format : `-?\d{1,3}(?:\.\d{1,2})?` — de `-999.99` à `999.99`, max 2 décimales.
- Contrainte : `min_target_temperature < max_target_temperature` strictement.

**`POST /equipments`**

```json
// Requête
{
  "name": "Chambre froide positive 1",
  "equipment_type": "CHAMBRE_FROIDE_POSITIVE",
  "min_target_temperature": "0.00",
  "max_target_temperature": "4.00",
  "establishment_id": "22222222-2222-4222-8222-222222222222"
}

// Réponse 201
{
  "id": "33333333-3333-4333-8333-333333333333",
  "name": "Chambre froide positive 1",
  "equipment_type": "CHAMBRE_FROIDE_POSITIVE",
  "min_target_temperature": "0.00",
  "max_target_temperature": "4.00",
  "establishment_id": "22222222-...",
  "establishment_site_name": "Restaurant Le Provençal",
  "is_active": true
}
```

---

### 4.5 Catalogue — Fournisseurs et produits

Module: `app/modules/catalog/router.py` (protégé par `require_feature(Feature.SUPPLIERS)`).

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `GET` | `/suppliers` | `CurrentSite` | Liste fournisseurs (filtres `include_inactive`, `status`) |
| `GET` | `/suppliers/{supplier_id}` | `CurrentSite` | Détail fournisseur |
| `POST` | `/suppliers` | `CurrentSite` | Crée un fournisseur |
| `PATCH` | `/suppliers/{supplier_id}` | `CurrentSite` | Met à jour un fournisseur |
| `DELETE` | `/suppliers/{supplier_id}` | `CurrentSite` | Soft-delete fournisseur |
| `GET` | `/products` | `CurrentSite` | Liste produits catalogue (filtre `supplier_id`) |
| `GET` | `/products/{product_id}` | `CurrentSite` | Détail produit |
| `POST` | `/products` | `CurrentSite` | Crée un produit catalogue |
| `PATCH` | `/products/{product_id}` | `CurrentSite` | Met à jour un produit |
| `DELETE` | `/products/{product_id}` | `CurrentSite` | Soft-delete produit |

---

### 4.6 Réceptions — Sessions de livraison

Module: `app/modules/receptions/router.py` (protégé par `require_feature(Feature.RECEPTIONS)`).

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `GET` | `/products` | `CurrentSite` | Liste produits utilisables en réception |
| `POST` | `/products` | `CurrentSite` | Crée un produit côté réception |
| `PATCH` | `/products/{product_id}` | `CurrentSite` | Met à jour un produit côté réception |
| `DELETE` | `/products/{product_id}` | `CurrentSite` | Soft-delete produit côté réception |
| `POST` | `/reception-sessions` | `CurrentSite` + `CurrentOperator` | Ouvre une session de réception (multipart, photo BL optionnelle) |
| `GET` | `/reception-sessions/{session_id}` | `CurrentSite` | Détail session + lignes scannées |
| `POST` | `/reception-sessions/{session_id}/items` | `CurrentSite` + `CurrentOperator` | Ajoute une ligne produit, ouvre une non-conformité si non conforme |
| `PATCH` | `/reception-sessions/{session_id}/close` | `CurrentSite` | Clôture une session de réception |

---

### 4.7 Nettoyage — Routines et logs

Module: `app/modules/cleaning/router.py` (protégé par `require_feature(Feature.CLEANING)`).

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `GET` | `/cleaning-zones` | `CurrentSite` | Liste zones de nettoyage |
| `POST` | `/cleaning-zones` | `CurrentSite` | Crée une zone |
| `DELETE` | `/cleaning-zones/{zone_id}` | `CurrentSite` | Supprime une zone |
| `GET` | `/cleaning-routines` | `CurrentSite` | Liste routines |
| `POST` | `/cleaning-routines` | `CurrentSite` | Crée une routine |
| `GET` | `/cleaning-routines/current` | `CurrentSite` | Retourne la routine courante (ou `schedule_type`) |
| `GET` | `/cleaning-routines/{routine_id}` | `CurrentSite` | Détail routine + état des tâches |
| `DELETE` | `/cleaning-routines/{routine_id}` | `CurrentSite` | Supprime une routine |
| `POST` | `/cleaning-routines/{routine_id}/tasks` | `CurrentSite` | Ajoute une tâche modèle |
| `DELETE` | `/cleaning-tasks/{task_id}` | `CurrentSite` | Supprime une tâche modèle |
| `POST` | `/cleaning-logs/bulk` | `CurrentSite` + `CurrentOperator` | Soumet un lot de logs de nettoyage |

---

### 4.8 Utilisateurs et rôles

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `GET` | `/roles` | `CurrentSite` | Liste tous les rôles disponibles |
| `GET` | `/users` | `CurrentSite` | Liste les utilisateurs de l'organisation |
| `POST` | `/users` | `CurrentSite` | Crée un utilisateur et l'affecte à un ou plusieurs établissements |
| `PATCH` | `/users/{utilisateur_id}` | `CurrentSite` | Met à jour un utilisateur |
| `DELETE` | `/users/{utilisateur_id}` | `CurrentSite` | Soft-delete (ou hard avec `?hard_delete=true`) |

**Règles de validation (mot de passe) :**
- Longueur : 12-72 caractères.
- Contenu obligatoire : au moins une minuscule, une majuscule, un chiffre, un caractère spécial.

**PIN code :**
- Exactement 4 chiffres (`^\d{4}$`).
- Stocké en bcrypt. Maximum 72 bytes UTF-8 (limitation bcrypt).

**Soft delete vs hard delete :**
- `DELETE /users/{id}` sans paramètre → pose `deleted_at = now()`. L'utilisateur disparaît des listes mais les données historiques sont conservées.
- `DELETE /users/{id}?hard_delete=true` → suppression physique. Requiert le rôle platform admin (via `ensure_platform_admin_access`).

**`POST /users`**

```json
// Requête
{
  "last_name": "Dupont",
  "first_name": "Jean",
  "email": "jean.dupont@restaurant.fr",
  "password": "MonMotDePasse1!",
  "pin_code": "1234",
  "role_id": "55555555-5555-4555-8555-555555555555",
  "establishment_ids": [
    "22222222-2222-4222-8222-222222222222"
  ]
}

// Réponse 201
{
  "user_id": "4b51ad67-4805-43e9-91a3-2fc60f930636",
  "email": "jean.dupont@restaurant.fr",
  "establishment_ids": ["22222222-..."]
}
```

---

### 4.9 Organisation et administration

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `POST` | `/organisations` | `X-Platform-Admin-Key` | **Crée une nouvelle organisation (tenant SaaS)** |
| `GET` | `/organisations/{id}/subscriptions` | `CurrentOrg` | Liste les abonnements Stripe de l'organisation |
| `POST` | `/organisations/{id}/establishments` | `CurrentOrg` | Crée un établissement dans l'organisation |
| `GET` | `/organisations/{id}/overview` | `CurrentOrg` | Vue d'ensemble : sites, managers, employés |
| `GET` | `/establishments/{id}/users/assigned` | `CurrentSite` | Liste les utilisateurs assignés à un établissement (vue admin) |
| `POST` | `/establishments/{id}/assignments` | `CurrentSite` | Assigne un utilisateur avec un rôle à l'établissement |
| `DELETE` | `/establishments/{id}` | `CurrentSite` | Soft-delete établissement |

> **Important :** `DELETE /establishments/{id}` rejette avec `400` si l'`etablissement_id` est celui du token courant (protection anti auto-suppression).

**`POST /organisations`** — requiert le header `X-Platform-Admin-Key`.

```json
// Requête
{
  "nom_entite": "Groupe Restauration Sud",
  "type_secteur": "PRIVE",
  "identifiant_legal": "12345678901234",
  "admin_login_email": "admin@groupe-restauration.fr",
  "admin_password": "AdminMotDePasse1!"
}

// Réponse 201
{
  "id": "11111111-1111-4111-8111-111111111111",
  "nom_entite": "Groupe Restauration Sud",
  "type_secteur": "PRIVE",
  "identifiant_legal": "12345678901234",
  "admin_login_email": "admin@groupe-restauration.fr"
}
```

**`POST /establishments/{id}/assignments`**

```json
// Requête
{
  "utilisateur_id": "4b51ad67-4805-43e9-91a3-2fc60f930636",
  "role_id": "55555555-5555-4555-8555-555555555555",
  "poste_principal": "Chef de cuisine",
  "is_active": true
}
```

> **Sécurité :** l'utilisateur affecté doit appartenir à la même organisation que l'établissement cible. Une tentative d'affectation cross-tenant retourne `404`.

---

### 4.10 Time clock — Pointage RH

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `POST` | `/time-clock-events` | `CurrentSite` + `CurrentOperator` | Enregistre un événement de pointage |

**Types d'événements (`TypeEvenementPointage`) :** `CLOCK_IN` · `BREAK_START` · `BREAK_END` · `CLOCK_OUT`

```json
// Requête
{ "type_evenement": "CLOCK_IN" }

// Réponse 201
{
  "id": "eeee0001-...",
  "etablissement_id": "22222222-...",
  "utilisateur_id": "4b51ad67-...",
  "type_evenement": "CLOCK_IN",
  "pointe_at": "2026-06-03T08:00:00+02:00"
}
```

Le timestamp `pointe_at` est automatiquement calculé via `now_for_site(establishment.timezone)`.

---

### 4.11 Système

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `GET` | `/health` | Aucune | Probe de santé API + base de données |
| `GET` | `/metrics` | `Bearer METRICS_TOKEN` (si configuré) | Métriques Prometheus |

```json
// GET /health — 200 OK
{ "status": "ok", "database": "ok" }

// GET /health — 503 si BD indisponible
{ "detail": { "status": "error", "database": "unavailable" } }
```

---

### Codes HTTP retournés

| Code | Signification | Contextes typiques |
|------|---------------|--------------------|
| `200` | Succès | GET, PATCH, actions workflow |
| `201` | Ressource créée | POST avec création |
| `204` | Suppression réussie | DELETE |
| `400` | Requête invalide | Auto-suppression établissement courant, format invalide |
| `401` | Non authentifié | Token absent/expiré, PIN invalide, Platform Admin Key incorrecte |
| `403` | Accès refusé | Scope établissement/organisation différent, permissions insuffisantes |
| `404` | Introuvable | Ressource absente ou hors scope |
| `409` | Conflit d'état | Transition workflow invalide, doublon email, action corrective déjà existante |
| `422` | Entité non traitable | Description action corrective vide, validation Pydantic |
| `503` | Service indisponible | Base de données inaccessible |

---

## 5. Modèle de données

### Schéma des relations

```
Organisation ──1:N── Abonnement
Organisation ──1:N── Etablissement
                         │
          ┌──────────────┼──────────────┐
          │              │              │
         N:M          1:N            1:N
   (AffectationSite) Equipement    Pointage
          │              │
         N:1           1:N
        Role      ReleveTemperature
                        │
                       1:0..1
                   NonConformity
                        │
                       1:0..1
                  ActionCorrective
```

### `organisations`

| Colonne | Type PostgreSQL | Contraintes | Description |
|---------|----------------|-------------|-------------|
| `id` | `UUID` | PK | — |
| `nom_entite` | `VARCHAR(255)` | NOT NULL | Raison sociale |
| `type_secteur` | `type_secteur` (enum) | NOT NULL | `PRIVE` ou `PUBLIC` |
| `identifiant_legal` | `VARCHAR(64)` | nullable | SIRET ou équivalent |
| `admin_login_email` | `VARCHAR(320)` | UNIQUE, nullable | Email de connexion admin org |
| `admin_password_hash` | `VARCHAR(255)` | nullable | Bcrypt hash |
| `email_facturation` | `VARCHAR(320)` | nullable | — |
| `adresse_facturation` | `VARCHAR(1024)` | nullable | — |
| `numero_tva_intracommunautaire` | `VARCHAR(32)` | nullable | — |
| `stripe_customer_id` | `VARCHAR(255)` | UNIQUE, nullable | ID client Stripe |
| `created_at` / `updated_at` | `TIMESTAMPTZ` | NOT NULL | Horodatage auto |

### `abonnements`

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | — |
| `organisation_id` | `UUID` | FK → `organisations`, CASCADE, INDEX | — |
| `stripe_subscription_id` | `VARCHAR(255)` | UNIQUE, NOT NULL | — |
| `stripe_price_id` | `VARCHAR(255)` | NOT NULL | — |
| `statut` | `statut_abonnement` (enum) | NOT NULL | Voir valeurs ci-dessous |
| `intervalle` | `VARCHAR(32)` | NOT NULL | `month`, `year`, etc. |
| `features_limits` | `JSONB` | NOT NULL, défaut `{}` | Quotas features |
| `date_debut` | `TIMESTAMPTZ` | NOT NULL | — |
| `date_fin_periode` | `TIMESTAMPTZ` | nullable | `null` si actif en cours |

Valeurs `statut_abonnement` : `TRIALING` · `ACTIVE` · `PAST_DUE` · `CANCELED` · `INCOMPLETE` · `INCOMPLETE_EXPIRED` · `UNPAID` · `PAUSED`

### `etablissements`

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | — |
| `organisation_id` | `UUID` | FK → `organisations`, CASCADE, INDEX | — |
| `nom_site` | `VARCHAR(255)` | NOT NULL | — |
| `adresse` | `VARCHAR(1024)` | nullable | — |
| `siret` | `VARCHAR(14)` | UNIQUE, nullable | — |
| `type_activite` | `VARCHAR(128)` | nullable | Ex : restaurant, traiteur |
| `timezone` | `VARCHAR(64)` | NOT NULL, défaut `Europe/Paris` | IANA tz name |
| `telephone_site` | `VARCHAR(32)` | nullable | — |
| `deleted_at` | `TIMESTAMPTZ` | nullable | **Soft-delete** |

### `utilisateurs`

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | — |
| `nom` | `VARCHAR(255)` | NOT NULL | Nom de famille |
| `prenom` | `VARCHAR(255)` | NOT NULL | Prénom |
| `email` | `VARCHAR(320)` | UNIQUE, INDEX, NOT NULL | — |
| `telephone_mobile` | `VARCHAR(32)` | nullable | — |
| `mot_de_passe_hash` | `VARCHAR(255)` | NOT NULL | Bcrypt |
| `code_pin` | `VARCHAR(255)` | nullable | Bcrypt du PIN 4 chiffres |
| `derniere_connexion` | `TIMESTAMPTZ` | nullable | — |
| `deleted_at` | `TIMESTAMPTZ` | nullable | **Soft-delete** |

### `roles`

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | — |
| `nom_role` | `VARCHAR(128)` | UNIQUE, NOT NULL | Ex : `SITE_MANAGER`, `SITE_EMPLOYEE` |
| `permissions` | `JSONB` | NOT NULL, défaut `{}` | Map de permissions (`"manager": true`, etc.) |

### `affectations_site`

**Clé primaire composite** : `(utilisateur_id, etablissement_id, role_id)`

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `utilisateur_id` | `UUID` | PK, FK → `utilisateurs`, CASCADE | — |
| `etablissement_id` | `UUID` | PK, FK → `etablissements`, CASCADE | — |
| `role_id` | `UUID` | PK, FK → `roles`, **RESTRICT** | — |
| `poste_principal` | `VARCHAR(128)` | nullable | Titre de poste |
| `affecte_le` | `TIMESTAMPTZ` | NOT NULL, `now()` | Date d'affectation |
| `is_active` | `BOOLEAN` | NOT NULL, défaut `true` | Flag de déactivation |

### `equipements`

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | — |
| `etablissement_id` | `UUID` | FK → `etablissements`, CASCADE, INDEX | — |
| `nom` | `VARCHAR(255)` | NOT NULL | Nom descriptif |
| `type_equipement` | `type_equipement` (enum) | NOT NULL, défaut `AUTRE` | 11 valeurs |
| `temperature_min_cible` | `NUMERIC(6,2)` | NOT NULL | Seuil bas en °C |
| `temperature_max_cible` | `NUMERIC(6,2)` | NOT NULL | Seuil haut en °C |
| `deleted_at` | `TIMESTAMPTZ` | nullable | **Soft-delete** |

### `releves_temperature`

**Table d'audit immuable** — pas de soft-delete.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | — |
| `etablissement_id` | `UUID` | FK → `etablissements`, CASCADE, INDEX | — |
| `equipement_id` | `UUID` | FK → `equipements`, **RESTRICT**, INDEX | RESTRICT : empêche la suppression d'un équipement avec des relevés |
| `utilisateur_id` | `UUID` | FK → `utilisateurs`, **RESTRICT**, INDEX | — |
| `valeur_mesuree` | `NUMERIC(6,2)` | NOT NULL | Température mesurée en °C |
| `is_conforme` | `BOOLEAN` | NOT NULL | Calculé à la création, jamais modifié |
| `source` | `source_releve` (enum) | NOT NULL | `MANUEL` ou `IOT` |
| `mesure_effectuee_at` | `TIMESTAMPTZ` | NOT NULL | Timestamp de la mesure (timezone site) |

### `non_conformities`

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | — |
| `establishment_id` | `UUID` | FK → `etablissements`, CASCADE, INDEX | — |
| `workflow_type` | `workflow_type` (enum) | NOT NULL | `TEMPERATURE` (extensible) |
| `status` | `nonconformity_status` (enum) | NOT NULL, défaut `OPEN` | Machine d'état |
| `source_record_id` | `UUID` | FK → `releves_temperature`, RESTRICT, UNIQUE, INDEX, nullable | Lien vers la mesure déclenchante |
| `opened_by_id` | `UUID` | FK → `utilisateurs`, RESTRICT, INDEX | Opérateur ayant déclenché |
| `opened_at` | `TIMESTAMPTZ` | NOT NULL | = `mesure_effectuee_at` du relevé |
| `assigned_to_id` | `UUID` | FK → `utilisateurs`, RESTRICT, nullable | Opérateur ayant acknowledge |
| `assigned_at` | `TIMESTAMPTZ` | nullable | — |
| `resolved_at` | `TIMESTAMPTZ` | nullable | = `signee_at` de l'action corrective |
| `closed_by_id` | `UUID` | FK → `utilisateurs`, RESTRICT, nullable | Manager ayant clôturé |
| `closed_at` | `TIMESTAMPTZ` | nullable | — |
| `closing_comment` | `TEXT` | nullable | Note de clôture manager |

### `actions_correctives`

**Contrainte UNIQUE sur `nonconformity_id`** : une seule action corrective par ticket.

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | — |
| `nonconformity_id` | `UUID` | FK → `non_conformities`, CASCADE, UNIQUE, INDEX | — |
| `utilisateur_id` | `UUID` | FK → `utilisateurs`, RESTRICT, INDEX | Opérateur signataire |
| `description` | `TEXT` | NOT NULL | Description de l'action réalisée |
| `photo_s3_key` | `VARCHAR(1024)` | nullable | Clé S3 de la photo de preuve |
| `signee_at` | `TIMESTAMPTZ` | NOT NULL | Timestamp de signature |

### `pointages`

| Colonne | Type | Contraintes | Description |
|---------|------|-------------|-------------|
| `id` | `UUID` | PK | — |
| `etablissement_id` | `UUID` | FK → `etablissements`, CASCADE, INDEX | — |
| `utilisateur_id` | `UUID` | FK → `utilisateurs`, RESTRICT, INDEX | — |
| `type_evenement` | `type_evenement_pointage` (enum) | NOT NULL | `CLOCK_IN` · `BREAK_START` · `BREAK_END` · `CLOCK_OUT` |
| `pointe_at` | `TIMESTAMPTZ` | NOT NULL | Timestamp en timezone du site |

### Stratégie soft-delete

| Tables avec `deleted_at` (soft-delete) | Tables immuables (audit-trail) |
|----------------------------------------|-------------------------------|
| `etablissements`, `utilisateurs`, `equipements` | `releves_temperature`, `non_conformities`, `actions_correctives`, `pointages` |

Les tables immuables contiennent des preuves HACCP légalement nécessaires. Elles ne peuvent pas être supprimées via l'API publique (hard-delete nécessite la Platform Admin Key).

---

## 6. Schémas de requête / réponse

### `TemperatureRecordCreate`

```json
{
  "equipment_id": "33333333-3333-4333-8333-333333333333",
  "measured_value": "3.80",
  "source": "MANUEL",
  "measured_at": "2026-06-03T09:30:00+02:00"
}
```

- `measured_value` : format `^-?\d{1,3}(?:\.\d{1,2})?$` — ex. `-18`, `4.5`, `3.80`
- `source` : `MANUEL` (défaut) ou `IOT`
- `measured_at` : optionnel, ISO 8601 avec fuseau. Si absent → `now()` en timezone de l'établissement

### `NonConformityItemResponse` — champs complets

```json
{
  "id": "cccc0001-cccc-4ccc-8ccc-cccccccccccc",
  "workflow_type": "TEMPERATURE",
  "status": "RESOLVED",
  "opened_by_name": "Jean Dupont",
  "opened_at": "2026-06-03T09:30:00+02:00",
  "assigned_to_name": "Marie Martin",
  "assigned_at": "2026-06-03T09:45:00+02:00",
  "resolved_at": "2026-06-03T10:15:00+02:00",
  "closed_by_name": null,
  "closed_at": null,
  "closing_comment": null,
  "source_record_id": "aaaa0001-...",
  "equipment_id": "33333333-...",
  "equipment_name": "Chambre froide positive 1",
  "measured_value": "14.50",
  "temperature_min": "0.00",
  "temperature_max": "4.00",
  "deviation_celsius": "10.50",
  "source": "MANUEL",
  "corrective_action_id": "dddd0001-...",
  "corrective_action_description": "Produits isolés, maintenance prévenue.",
  "corrective_action_signed_at": "2026-06-03T10:15:00+02:00",
  "corrective_action_photo_url": "http://localhost:9000/haccp-documents/haccp/22222222-.../corrective-actions/uuid.jpg"
}
```

> Les champs `equipment_*`, `measured_value`, `temperature_*`, `deviation_celsius`, `source` sont `null` pour les workflows non-température (futurs).

### `UserCreateRequest`

```json
{
  "last_name": "Dupont",
  "first_name": "Jean",
  "email": "jean.dupont@restaurant.fr",
  "password": "MonMotDePasse1!",
  "pin_code": "1234",
  "role_id": "55555555-5555-4555-8555-555555555555",
  "establishment_ids": ["22222222-2222-4222-8222-222222222222"]
}
```

Règles mot de passe : longueur 12-72 chars · au moins une minuscule · une majuscule · un chiffre · un caractère spécial.

### `OrganisationCreateRequest`

```json
{
  "nom_entite": "Groupe Restauration Sud",
  "type_secteur": "PRIVE",
  "identifiant_legal": "12345678901234",
  "admin_login_email": "admin@groupe-restauration.fr",
  "admin_password": "AdminMotDePasse1!"
}
```

`type_secteur` : `PRIVE` ou `PUBLIC`.

### `CloseNonConformityRequest`

```json
{
  "closing_comment": "Vérification réalisée le 03/06/2026, conformité rétablie."
}
```

Le champ `closing_comment` est optionnel (`null` accepté).

---

## 7. Variables d'environnement

Le fichier `.env.example` contient toutes les valeurs par défaut pour le développement local.

### Base de données

| Variable | Type | Défaut local | Description |
|----------|------|-------------|-------------|
| `DATABASE_URL` | `str` | `postgresql+asyncpg://haccp_user:haccp_password@db:5432/haccp_control` | URL SQLAlchemy async PostgreSQL |

### JWT

| Variable | Type | Défaut | Production |
|----------|------|--------|-----------|
| `JWT_SECRET_KEY` | `str` (min 32 chars) | `change-me-in-production-local-secret` | **⚠️ Changer absolument** |
| `JWT_ALGORITHM` | `str` | `HS256` | Algorithme de signature |
| `ESTABLISHMENT_ACCESS_TOKEN_EXPIRE_HOURS` | `int` (1-24) | `12` | Durée de vie du device token |

### Plateforme

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `ENVIRONMENT` | `str` | `local` | `local`, `staging`, `production` |
| `APP_VERSION` | `str` | `0.0.0-local` | Version applicative remontée dans Sentry (`release`) |
| `PLATFORM_ADMIN_KEY` | `str` (min 32 chars) | `change-me-in-production-platform-secret` | **⚠️ Changer absolument** — clé pour créer des tenants et hard-delete |
| `BACKEND_CORS_ORIGINS` | `list[str]` | `["http://localhost:3000", "http://127.0.0.1:3000"]` | Origines autorisées CORS |

### Monitoring — Sentry

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `SENTRY_DSN` | `str \| None` | `None` | DSN Sentry — désactivé si absent |
| `SENTRY_TRACES_SAMPLE_RATE` | `float` (0.0-1.0) | `0.0` | Sampling des traces de performance |
| `SENTRY_PROFILES_SAMPLE_RATE` | `float` (0.0-1.0) | `0.0` | Sampling des profils CPU |

### Monitoring — Prometheus

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `METRICS_ENABLED` | `bool` | `true` | Active l'endpoint Prometheus |
| `METRICS_ENDPOINT` | `str` | `/metrics` | Path d'exposition des métriques |
| `METRICS_TOKEN` | `str \| None` | `None` | Token Bearer pour `/metrics`. `None` = endpoint public |

### S3 / MinIO

| Variable | Type | Défaut | Description |
|----------|------|--------|-------------|
| `AWS_ACCESS_KEY_ID` | `str` | `minioadmin` | Clé d'accès S3 |
| `AWS_SECRET_ACCESS_KEY` | `str` | `minioadmin` | Secret S3 |
| `AWS_REGION` | `str` | `eu-west-3` | Région AWS (ignorée par MinIO) |
| `AWS_ENDPOINT_URL` | `str` | `http://minio:9000` | Endpoint **interne** Docker |
| `S3_PUBLIC_ENDPOINT_URL` | `str` | `http://localhost:9000` | Endpoint **public** pour construire les URLs |
| `S3_BUCKET_NAME` | `str` | `haccp-documents` | Nom du bucket |

### Checklist production

Avant tout déploiement en production, **ces 5 variables doivent impérativement être modifiées** :

```bash
JWT_SECRET_KEY=<secret aléatoire ≥ 32 chars>
PLATFORM_ADMIN_KEY=<secret aléatoire ≥ 32 chars, différent de JWT_SECRET_KEY>
DATABASE_URL=postgresql+asyncpg://<user>:<password>@<host>:5432/<db>
SENTRY_DSN=https://<key>@o<org>.ingest.sentry.io/<project>
METRICS_TOKEN=<secret aléatoire>
```

En `staging` et `production`, l'application applique aussi une validation stricte au démarrage:

- Refus des secrets faibles pour `JWT_SECRET_KEY` et `PLATFORM_ADMIN_KEY` (marqueurs interdits: `change-me`, `changeme`, `default`, `example`, `placeholder`, `secret`, `minioadmin`).
- Refus des credentials S3 par défaut (`AWS_ACCESS_KEY_ID=minioadmin` ou `AWS_SECRET_ACCESS_KEY=minioadmin`).

### 7.1 Feature flags et limites de plan

La configuration par établissement est stockée dans `etablissements.settings` (JSONB), structurée par `EstablishmentSettings`.

Features disponibles (`Feature`):

- `timeclock`
- `haccp_temperature`
- `cleaning`
- `receptions`
- `nonconformities`
- `suppliers`
- `operators`

Endpoints associés:

| Méthode | Path | Auth | Description |
|---------|------|------|-------------|
| `GET` | `/establishment-settings` | `CurrentSite` | Retourne les toggles effectifs du site |
| `PATCH` | `/establishment-settings` | `CurrentSite` (admin org) | Met à jour partiellement les toggles |
| `GET` | `/plan-limits` | `CurrentSite` | Retourne limites de plan et features activées |

Le guard `require_feature(Feature.X)` est appliqué sur plusieurs routeurs. Quand la fonctionnalité est désactivée pour le site, l'API retourne `403 Forbidden`.

---

## 8. Migrations Alembic

### Chaîne des migrations

```
bf5974834806  ─►  4d2b6cf6dca1  ─►  6f8ea9a2b8a7  ─►  7c19f57a12ab  ─►  a1b2c3d4e5f6
    │                   │                  │                  │                  │
  Schema          Type équipement    Enum étendu       Admin org          Non-conformités
  initial          + 4 types          + 7 types         credentials         + ActionCorrective
```

| Révision | Objectif |
|----------|---------|
| `bf5974834806` | Schéma opérationnel initial : toutes les tables de base, FK, index |
| `4d2b6cf6dca1` | Ajout de l'enum `type_equipement` (4 premiers types) + colonne sur `equipements` |
| `6f8ea9a2b8a7` | Extension de l'enum : `ALTER TYPE type_equipement ADD VALUE IF NOT EXISTS '...'` (7 types supplémentaires) |
| `7c19f57a12ab` | Ajout de `admin_login_email` + `admin_password_hash` sur `organisations` |
| `a1b2c3d4e5f6` | Création de `non_conformities`, migration de `actions_correctives.releve_id` → `nonconformity_id`, backfill des données existantes |

### Créer une nouvelle migration

```bash
# 1. Modifier le modèle SQLAlchemy dans app/models/
# 2. Générer la migration
docker exec haccp_api uv run alembic revision --autogenerate -m "add_colonne_to_table"
# 3. Vérifier et ajuster le fichier généré dans alembic/versions/
# 4. Appliquer
docker exec haccp_api uv run alembic upgrade head
```

### Pattern : ajouter un enum PostgreSQL natif

```python
def upgrade() -> None:
    # Création idempotente via DO block (pas de CREATE TYPE IF NOT EXISTS)
    op.execute("""
        DO $$ BEGIN
            CREATE TYPE mon_enum AS ENUM ('VALEUR_1', 'VALEUR_2');
        EXCEPTION WHEN duplicate_object THEN NULL;
        END $$;
    """)

    # create_type=False évite qu'op.create_table() tente de re-créer l'enum
    mon_enum = postgresql.ENUM('VALEUR_1', 'VALEUR_2', name='mon_enum', create_type=False)

    op.add_column('ma_table', sa.Column('ma_colonne', mon_enum, nullable=False, server_default='VALEUR_1'))

def downgrade() -> None:
    op.drop_column('ma_table', 'ma_colonne')
    postgresql.ENUM(name='mon_enum').drop(op.get_bind(), checkfirst=True)
```

### Pattern : migration avec data backfill

```python
def upgrade() -> None:
    # 1. Créer la nouvelle table
    op.create_table('nouvelle_table', ...)

    # 2. Backfill des données
    op.execute("""
        INSERT INTO nouvelle_table (id, ...)
        SELECT gen_random_uuid(), ...
        FROM table_source
        WHERE condition
    """)

    # 3. Rendre les colonnes NOT NULL après backfill
    op.alter_column('nouvelle_table', 'colonne_critique', nullable=False)
```

---

## 9. Observabilité

### 9.1 Health check

```http
GET /health
```

```json
// 200 OK — API et BD opérationnelles
{ "status": "ok", "database": "ok" }

// 503 Service Unavailable — BD inaccessible
{ "detail": { "status": "error", "database": "unavailable" } }
```

Utilisé par les probes Kubernetes/Docker et les monitors de disponibilité.

### 9.2 Prometheus

**Endpoint :** `GET /metrics` (gzip, format OpenMetrics)

Si `METRICS_TOKEN` est configuré :
```http
GET /metrics
Authorization: Bearer <METRICS_TOKEN>
```

**3 métriques custom** (route migration tracking) :

| Métrique | Type | Labels | Description |
|----------|------|--------|-------------|
| `route_migration_requests_total` | Counter | `route_family`, `method`, `status_class` | Total requêtes par famille (legacy/rest_v1) |
| `route_migration_errors_total` | Counter | `route_family`, `method`, `status_code` | Total erreurs HTTP |
| `route_migration_duration_seconds` | Histogram | `route_family`, `method` | Durée des requêtes |

`route_family` vaut `legacy` (anciens paths) ou `rest_v1` (nouveaux paths).

La configuration Prometheus scrape l'API via `infra/prometheus.yml`. Si `METRICS_TOKEN` est utilisé, décommenter le bloc `authorization` dans ce fichier.

### 9.3 Sentry

Sentry est activé si `SENTRY_DSN` est défini. Intégrations actives :

- **FastAPI** : trace les transactions par endpoint
- **Starlette** : trace les middlewares
- **SQLAlchemy** : trace les requêtes SQL

`send_default_pii=False` — aucune donnée personnelle (email, IP) n'est envoyée à Sentry.

Pour activer le profiling en production :

```bash
SENTRY_TRACES_SAMPLE_RATE=0.1   # 10% des transactions
SENTRY_PROFILES_SAMPLE_RATE=0.1 # 10% des profils CPU
```

---

## 10. Routes dépréciées

Les anciennes routes existent encore dans la table de mapping de `app/core/deprecation.py`. Quand une route dépréciée est appelée, la réponse inclut automatiquement les headers RFC 8594 :

```http
Deprecation: true
Sunset: <date + 90 jours>
Link: </api/v1/nonconformities>; rel="successor-version", </api/v1/docs/migration-rest-v1>; rel="deprecation"
```

### Table de migration complète

| Route obsolète | Nouvelle route |
|----------------|---------------|
| `POST /api/v1/auth/login/organisation` | `POST /api/v1/organisation-sessions` |
| `POST /api/v1/auth/login/manager` | `POST /api/v1/establishment-sessions` |
| `GET /api/v1/auth/establishments/{id}` | `GET /api/v1/establishments/{id}` |
| `GET /api/v1/auth/operators` | `GET /api/v1/establishments/{id}/users?role=SITE_EMPLOYEE` |
| `POST /api/v1/auth/me-operator` | `POST /api/v1/operator-sessions` |
| `GET /api/v1/admin/roles` | `GET /api/v1/roles` |
| `GET /api/v1/admin/users` | `GET /api/v1/users` |
| `PATCH /api/v1/admin/users/{id}` | `PATCH /api/v1/users/{id}` |
| `GET /api/v1/admin/equipment` | `GET /api/v1/equipments` |
| `PATCH /api/v1/admin/equipment/{id}` | `PATCH /api/v1/equipments/{id}` |
| `GET /api/v1/haccp/equipment` | `GET /api/v1/equipments` |
| `POST /api/v1/haccp/temperature-records` | `POST /api/v1/temperature-records` |
| `POST /api/v1/haccp/temperature-records/{id}/corrective-actions` | `POST /api/v1/nonconformities/{id}/corrective-action` |
| `POST /api/v1/rh/time-clock-events` | `POST /api/v1/time-clock-events` |
| `GET /api/v1/admin/alerts` | `GET /api/v1/nonconformities` |
| `GET /api/v1/admin/alerts/stats` | `GET /api/v1/nonconformities/stats` |
| `GET /api/v1/temperature-alerts` | `GET /api/v1/nonconformities` |
| `GET /api/v1/temperature-alerts/metrics` | `GET /api/v1/nonconformities/stats` |
| `GET /api/v1/organisation/overview` | `GET /api/v1/organisations/{id}/overview` |
| `GET /api/v1/organisations/{id}/abonnements` | `GET /api/v1/organisations/{id}/subscriptions` |
| `GET /api/v1/organisations/{id}/etablissements` | `POST /api/v1/organisations/{id}/establishments` |
| `GET /api/v1/etablissements/{id}/equipements` | `GET /api/v1/establishments/{id}/equipments` |
| `GET /api/v1/etablissements/{id}/utilisateurs` | `GET /api/v1/establishments/{id}/users` |
| `POST /api/v1/etablissements/{id}/affectations` | `POST /api/v1/establishments/{id}/assignments` |

---

## 11. Stockage S3 / MinIO

Les photos de preuve des actions correctives sont stockées dans MinIO (compatible S3).

### Configuration

- **Endpoint interne** (conteneur Docker) : `http://minio:9000` — utilisé pour les uploads
- **Endpoint public** (navigateur) : `http://localhost:9000` — utilisé pour construire les URLs retournées dans l'API

### Formats acceptés

- Extensions : `.jpg`, `.jpeg`, `.png`
- MIME types : `image/jpeg`, `image/png`

Toute autre extension ou MIME type retourne `400 Bad Request`.

### Préfixe de stockage

```
haccp/{etablissement_id}/corrective-actions/{uuid}.jpg
```

Exemple de clé : `haccp/22222222-2222-4222-8222-222222222222/corrective-actions/7f3a4b12-....jpg`

### Génération d'URL publique

```python
# Formule : {S3_PUBLIC_ENDPOINT_URL}/{S3_BUCKET_NAME}/{key}
# Exemple  : http://localhost:9000/haccp-documents/haccp/22222222-.../uuid.jpg
```

L'URL est calculée à la volée à chaque réponse API — elle n'est pas stockée en base. Seule la **clé S3** (`photo_s3_key`) est persistée dans `actions_correctives`.

### Upload multipart

```bash
curl -X POST http://localhost:8001/api/v1/nonconformities/{id}/corrective-action \
  -H "Authorization: Bearer <token>" \
  -H "X-Device-Pin: 1234" \
  -H "X-Operator-Id: 4b51ad67-..." \
  -F "description=Produits isolés, chambre contrôlée" \
  -F "photo=@preuve.jpg"
```

---

## 12. Conventions de développement

### Nommage

- **Tout nouveau code en anglais** : noms de classes, fonctions, variables, colonnes de nouvelles tables.
- **Héritage français maintenu** dans les modèles existants (`etablissement_id`, `utilisateur_id`, `nom_site`, etc.) pour la compatibilité base de données.
- Les routes URL sont en anglais : `/nonconformities`, `/establishments`, `/equipments`.

### Pattern service (toutes les fonctions business logic)

```python
async def ma_fonction(
    db: AsyncSession,
    establishment: CurrentEstablishment,
    ...
) -> MaReponse:
    # 1. Garde d'accès (première ligne systématique)
    await ensure_admin_org_access(db, establishment)

    # 2. Requête SQL explicite (pas de lazy loading implicite)
    result = await db.execute(
        select(MonModele).where(
            MonModele.etablissement_id == establishment.etablissement_id,
            MonModele.deleted_at.is_(None),
        )
    )
    objet = result.scalar_one_or_none()
    if objet is None:
        raise HTTPException(status_code=404, detail="Objet introuvable.")

    # 3. Modifications et persistance
    objet.champ = nouvelle_valeur
    await db.commit()
    await db.refresh(objet)

    # 4. Mapping manuel ORM → schéma Pydantic
    return MaReponse(champ=objet.champ, ...)
```

### Utilitaires partagés à réutiliser

| Utilitaire | Fichier | Usage |
|-----------|---------|-------|
| `is_manager_role(role)` | `app/core/role_utils.py` | Vérifie si un rôle est manager (nom ou permission) |
| `is_platform_admin_role(role)` | `app/core/role_utils.py` | Vérifie si un rôle est platform admin |
| `now_for_site(timezone)` | `app/core/time_utils.py` | `datetime.now()` converti au fuseau de l'établissement |
| `TEMPERATURE_DECIMAL_PATTERN` | `app/modules/haccp/schemas.py` | Regex pour valider les températures côté HACCP |
| `validate_password_strength(value)` | `app/modules/personnel/schemas.py` | Règles mot de passe (lower+upper+digit+symbol) |
| `ensure_admin_org_access(db, establishment)` | `app/modules/personnel/service.py` | Vérifie que le manager a les droits sur l'établissement courant |

### Timestamps

Toujours utiliser `now_for_site(establishment.timezone)` pour les timestamps métier (relevés, pointages, actions correctives). Cela garantit que les horodatages sont cohérents avec le fuseau de l'établissement, même si le serveur est en UTC.

### Tests

```bash
# Depuis la racine du dépôt
docker compose exec api uv run pytest

# Avec une base de test différente
docker compose exec -e TEST_DATABASE_URL="postgresql+asyncpg://user:pwd@host:5432/db_test" api uv run pytest
```

La suite de tests utilise `haccp_control_test` par défaut.

---

## 13. CI/CD

Le workflow principal est défini dans `.github/workflows/ci-cd.yml`.

### 13.1 Validation (PR et push main)

Job `validate-and-test` (répertoire de travail `backend/`):

1. `uv sync --frozen`
2. `uv run ruff format --check app alembic tests`
3. `uv run ruff check --output-format=github app alembic tests`
4. `uv run mypy app`
5. `uv run pytest`

Le `pytest` applique un seuil de couverture strict via `pyproject.toml`:

- `--cov=app --cov-branch --cov-report=term-missing --cov-fail-under=95`

### 13.2 Build et publication image

Job `build-and-deploy` (uniquement sur `push` vers `main` après validation):

1. Auth AWS via `configure-aws-credentials`
2. Login Amazon ECR
3. Build image `backend/Dockerfile`
4. Push tags `:<sha>` et `:latest` vers ECR

Variables/secrets attendus dans GitHub Actions:

- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `AWS_REGION`
- `ECR_REPOSITORY`

### 13.3 Checklist locale avant push

```bash
cd backend
uv sync --frozen
uv run ruff format --check app alembic tests
uv run ruff check app alembic tests
uv run mypy app
uv run pytest
```
