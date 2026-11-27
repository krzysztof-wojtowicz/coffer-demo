# Spec Delta

## REMOVED Requirements

### Requirement: Investment profile (F30)
**Reason**: The investment profile is kept; it is not part of the AI assistant.
**Migration**: Moved unchanged to the `portfolio` capability (`GET/PUT /api/profile` keep working).

### Requirement: Action engine
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.

### Requirement: Action catalog
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.

### Requirement: Report with computed numbers (F32, F33)
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.

### Requirement: Rule-based fallback (N08)
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.

### Requirement: Limits and abuse protection
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.

### Requirement: Privacy of data sent to the LLM (N03)
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.

### Requirement: Trace and history
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.

### Requirement: Investment ideas (F31, F36)
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.

### Requirement: Purchase impact (F37)
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.

### Requirement: Company research (F34, F35, N07)
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.

### Requirement: Budget actions (F12, F13, F15, F17, F31)
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.

### Requirement: Portfolio review
**Reason**: The AI assistant is removed during the refactor and will be rebuilt from scratch for local LLMs.
**Migration**: None. The endpoints under `/api/agent/*` are removed, and the stored runs, suggestions and usage counters are dropped by a migration.
