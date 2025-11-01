# API Documentation

## Overview
RESTful API for accessing platform functionality programmatically.

## Base URL
```
https://api.company.com/v1
```

## Authentication
All API requests require authentication using API keys.
```
Authorization: Bearer {api_key}
```

## Rate Limits
- Standard tier: 1,000 requests/hour
- Professional tier: 10,000 requests/hour
- Enterprise tier: 100,000 requests/hour

## Endpoints

### Users

#### Get User
```
GET /users/{user_id}
```

**Response:**
```json
{
  "id": "123",
  "email": "user@example.com",
  "name": "John Doe",
  "role": "admin",
  "created_at": "2024-01-15T10:00:00Z"
}
```

#### List Users
```
GET /users
```

**Query Parameters:**
- `page`: Page number (default: 1)
- `limit`: Results per page (default: 20, max: 100)
- `role`: Filter by role

### Projects

#### Create Project
```
POST /projects
```

**Request Body:**
```json
{
  "name": "Project Name",
  "description": "Project description",
  "owner_id": "123"
}
```

#### Get Project
```
GET /projects/{project_id}
```

### Data

#### Upload Data
```
POST /data/upload
Content-Type: multipart/form-data
```

#### Query Data
```
GET /data/query
```

**Query Parameters:**
- `filter`: JSON filter expression
- `sort`: Sort field and direction
- `limit`: Result limit

## Error Handling

### Error Response Format
```json
{
  "error": {
    "code": "ERROR_CODE",
    "message": "Human-readable error message",
    "details": {}
  }
}
```

### Common Error Codes
- `400`: Bad Request
- `401`: Unauthorized
- `403`: Forbidden
- `404`: Not Found
- `429`: Rate Limit Exceeded
- `500`: Internal Server Error

## Webhooks

### Event Types
- `user.created`
- `project.updated`
- `data.processed`
- `error.occurred`

### Webhook Payload
```json
{
  "event": "user.created",
  "timestamp": "2024-01-15T10:00:00Z",
  "data": {
    "user_id": "123",
    "email": "user@example.com"
  }
}
```

## SDKs
- Python SDK: `pip install company-sdk`
- JavaScript SDK: `npm install @company/sdk`
- Go SDK: `go get github.com/company/sdk-go`

## Support
- API Documentation: https://docs.company.com/api
- Support: api-support@company.com
- Status Page: https://status.company.com

