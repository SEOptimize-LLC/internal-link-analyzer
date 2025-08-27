# Internal Link Analyzer Workflow

```mermaid
flowchart TD
    A[User Input URLs] --> B{Validate URLs}
    B -->|Invalid| C[Show Error]
    B -->|Valid| D[Extract Domains]
    D --> E[Group URLs by Domain]
    E --> F[For Each Domain]
    F --> G[Check robots.txt]
    G -->|Blocked| H[Skip Domain]
    G -->|Allowed| I[Fetch Page Content]
    I --> J[Parse HTML & Extract Links]
    J --> K[Filter Internal Links]
    K --> L[Aggregate All Internal Links]
    L --> M[Group by Destination URL]
    M --> N{Find Duplicates >1 source}
    N -->|Duplicates Found| O[Create Results DataFrame]
    N -->|No Duplicates| P[No Issues Found]
    O --> Q[Display Results with Highlights]
    Q --> R[Export to CSV Option]
    P --> S[End]
    R --> S
    C --> T[End with Error]
    H --> U[Continue to Next Domain]
    U --> F