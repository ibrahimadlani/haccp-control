import { apiCall, bearerHeaders, operatorHeaders } from "./client"

export function uploadEstablishmentDocument(
  token,
  { pin, operatorId },
  { documentType, photo },
) {
  const form = new FormData()
  form.append("document_type", documentType)
  form.append("photo", photo)

  return apiCall("/api/v1/establishment-documents", {
    method: "POST",
    headers: operatorHeaders(token, pin, operatorId),
    body: form,
  })
}
