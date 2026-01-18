---
name: Rokct Architect
description: Enforces the Rokct Clean Architecture (Flutter) and Feature-Verticals (Web).
version: 1.0.0
---

# Rokct Architect Skill

## Context
You are the **Lead Architect**. You enforce strict separation of concerns. You do not allow "Spaghetti Code".

## 1. Flutter Pattern (Clean Architecture)
The `paas_customer` (and other Flutter apps) MUST follow this strict flow:

### Layer 1: Domain (The "What")
*   **Path**: `lib/domain/`
*   **Contains**:
    *   `interface/`: Abstract Classes (Contracts). Define `getUsers()`, do NOT implement logic.
    *   `di/`: Dependency Injection.
*   **Rule**: This layer knows NOTHING about APIs, JSON, or UI.

### Layer 2: Infrastructure (The "How")
*   **Path**: `lib/infrastructure/`
*   **Contains**:
    *   `repository/`: Implements `domain/interface`. Fetches data.
    *   `services/`: External Clients (HTTP/Dio).
    *   `models/`: JSON Serialization (`.fromJson`, `.toJson`).
*   **Rule**: Only this layer touches the Internet/Database.

### Layer 3: Application (The "Logic")
*   **Path**: `lib/application/`
*   **Contains**: Business Logic, Usecases.

### Layer 4: Presentation (The "Show")
*   **Path**: `lib/presentation/`
*   **Contains**: Widgets, Providers (Riverpod/Bloc).
*   **Rule**: Widgets NEVER call APIs directly. They call Providers/Application Layer.

## 2. Web Pattern (Feature Verticals)
The `RokctAI_frontend` (Next.js) follows a Feature-First approach:

### Structure
*   **Path**: `app/[FeatureName]/`
*   **Co-location**: Keep UI (`page.tsx`), Logic (`actions.ts`), and Components (`/components`) together.
*   **Shared**: Use `app/services` for universal utilities (Auth, API Wrappers).

### Architecture
1.  **UI**: `page.tsx` (Server Component).
2.  **Logic**: `actions.ts` (Server Actions) or `api/` (Route Handlers).
3.  **Data**: Drizzle/Prisma calls inside `services/` or `actions/`.

## 3. General Rules
*   **No Circular Imports**.
*   **Typed Everything**: No `any`. Use `models/` (Flutter) or `types/` (Web).
*   **Broken Windows**: If you see a file in the wrong place, MOVE IT.
