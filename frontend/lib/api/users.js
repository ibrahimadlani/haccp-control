import { apiCall, bearerHeaders } from "./client"

export function getRoles(token) {
  return apiCall("/api/v1/roles", { headers: bearerHeaders(token) })
}

export function getUsers(token) {
  return apiCall("/api/v1/users", { headers: bearerHeaders(token) })
}

export function createUser(token, body) {
  return apiCall("/api/v1/users", {
    method: "POST",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function updateUser(token, id, body) {
  return apiCall(`/api/v1/users/${id}`, {
    method: "PATCH",
    headers: bearerHeaders(token),
    body: JSON.stringify(body),
  })
}

export function deleteUser(token, id, hardDelete = false) {
  return apiCall(`/api/v1/users/${id}${hardDelete ? "?hard_delete=true" : ""}`, {
    method: "DELETE",
    headers: bearerHeaders(token),
  })
}
