# Enterprise Security Architecture Diagram

## High-Level Security Flow

```mermaid
graph TB
    subgraph "External Layer"
        U[User Input] --> IV[Input Validation]
        IV --> RA[Rate Analysis]
        RA --> SC[Security Check]
    end
    
    subgraph "Analysis Layer"
        SC --> SA[Semantic Analysis]
        SA --> NLP[NLP Processing]
        NLP --> TI[Threat Intelligence]
        TI --> CD[Context Detection]
    end
    
    subgraph "Sanitization Layer"
        CD --> TS[Template-Specific Sanitizer]
        TS --> CA[Context-Aware Processing]
        CA --> UC[Unicode Cleaning]
        UC --> ZW[Zero-Width Removal]
    end
    
    subgraph "Protection Layer"
        ZW --> MP[Multi-Layer Pipeline]
        MP --> RM[Runtime Monitoring]
        RM --> OV[Output Validation]
        OV --> AL[Audit Logging]
    end
    
    subgraph "LLM Layer"
        AL --> LLM[LLM Processing]
        LLM --> RV[Response Validation]
        RV --> AR[Audit Response]
    end
    
    subgraph "Monitoring Layer"
        AR --> SM[Security Metrics]
        SM --> AD[Alert Dashboard]
        AD --> IR[Incident Response]
    end
    
    style U fill:#ff9999
    style LLM fill:#99ff99
    style AD fill:#ffff99
    style IR fill:#ff9999
```

## Detailed Security Pipeline

```mermaid
flowchart TD
    Start([User Input]) --> LengthCheck{Length Valid?}
    LengthCheck -->|No| Block[Block Request]
    LengthCheck -->|Yes| CharCheck{Characters Valid?}
    
    CharCheck -->|No| Block
    CharCheck -->|Yes| RateCheck{Rate Limit OK?}
    
    RateCheck -->|No| Block
    RateCheck -->|Yes| SemanticCheck
    
    SemanticCheck -->|Suspicious| DeepAnalysis[Deep Analysis]
    SemanticCheck -->|Clean| Sanitize
    
    DeepAnalysis -->|Threat Detected| Block
    DeepAnalysis -->|False Positive| Sanitize
    
    Sanitize --> TemplateCheck{Template Type}
    TemplateCheck -->|Writer| WriterSan[Writer Sanitizer]
    TemplateCheck -->|Summarizer| SummarySan[Summarizer Sanitizer]
    TemplateCheck -->|Insights| InsightsSan[Insights Sanitizer]
    
    WriterSan --> ValidateJSON{JSON Valid?}
    SummarySan --> ValidateJSON
    InsightsSan --> ValidateJSON
    
    ValidateJSON -->|No| Block
    ValidateJSON -->|Yes| Monitor
    
    Monitor --> LLM[LLM Processing]
    LLM --> OutputCheck{Output Valid?}
    
    OutputCheck -->|No| Alert[Security Alert]
    OutputCheck -->|Yes| Log[Audit Log]
    
    Alert --> IR[Incident Response]
    Log --> Success([Success])
    
    Block --> LogBlock[Log Block Event]
    LogBlock --> Alert
    
    style Block fill:#ff6666
    style Alert fill:#ffaa66
    style Success fill:#66ff66
```

## Security Component Architecture

```mermaid
classDiagram
    class SecurityManager {
        -pipeline: SecurityPipeline
        -config: SecurityConfig
        -monitor: SecurityMonitor
        +validate(input: Any): SecurityResult
        +sanitize(text: str, context: str): str
    }
    
    class SecurityPipeline {
        -layers: List[SecurityLayer]
        +process(input: Any): SecurityResult
        +add_layer(layer: SecurityLayer)
    }
    
    class InputValidationLayer {
        -validator: InputValidator
        -rate_limiter: RateLimiter
        +validate(input: Any): ValidationResult
    }
    
    class SemanticAnalysisLayer {
        -analyzer: SemanticAnalyzer
        -threat_db: ThreatDatabase
        +analyze(text: str): AnalysisResult
    }
    
    class SanitizationLayer {
        -sanitizers: Dict[str, BaseSanitizer]
        +sanitize(text: str, context: str): str
    }
    
    class MonitoringLayer {
        -monitor: SecurityMonitor
        -logger: SecurityLogger
        +monitor(event: SecurityEvent)
    }
    
    class BaseSanitizer {
        <<interface>>
        +sanitize(text: str): str
    }
    
    class WriterSanitizer {
        +sanitize(text: str): str
    }
    
    class SummarizerSanitizer {
        +sanitize(messages: List[str]): List[str]
    }
    
    class InsightsSanitizer {
        +sanitize(memories: List[str]): List[str]
    }
    
    SecurityManager --> SecurityPipeline
    SecurityManager --> SecurityMonitor
    SecurityPipeline --> SecurityLayer
    InputValidationLayer ..|> SecurityLayer
    SemanticAnalysisLayer ..|> SecurityLayer
    SanitizationLayer ..|> SecurityLayer
    MonitoringLayer ..|> SecurityLayer
    SanitizationLayer --> BaseSanitizer
    WriterSanitizer ..|> BaseSanitizer
    SummarizerSanitizer ..|> BaseSanitizer
    InsightsSanitizer ..|> BaseSanitizer
```

## Data Flow Security

```mermaid
sequenceDiagram
    participant User
    participant API
    participant SecurityManager
    participant ValidationLayer
    participant SemanticLayer
    participant SanitizationLayer
    participant LLM
    participant Monitor
    
    User->>API: Send input
    API->>SecurityManager: validate()
    
    SecurityManager->>ValidationLayer: validate input
    ValidationLayer-->>SecurityManager: validation result
    
    alt validation passed
        SecurityManager->>SemanticLayer: analyze semantics
        SemanticLayer-->>SecurityManager: analysis result
        
        alt analysis clean
            SecurityManager->>SanitizationLayer: sanitize()
            SanitizationLayer-->>SecurityManager: sanitized text
            
            SecurityManager->>LLM: process sanitized input
            LLM-->>SecurityManager: response
            
            SecurityManager->>Monitor: log event
            SecurityManager-->>API: safe response
            
        else threat detected
            SecurityManager->>Monitor: security alert
            SecurityManager-->>API: block request
        end
        
    else validation failed
        SecurityManager->>Monitor: log block
        SecurityManager-->>API: reject request
    end
```

## Security Monitoring Dashboard

```mermaid
graph LR
    subgraph "Security Metrics"
        A[Requests/sec] --> D[Dashboard]
        B[Blocked Attacks] --> D
        C[False Positives] --> D
    end
    
    subgraph "Threat Intelligence"
        D --> E[Real-time Alerts]
        D --> F[Security Reports]
        D --> G[Incident Response]
    end
    
    subgraph "System Health"
        H[Performance Impact] --> D
        I[Error Rates] --> D
        J[System Load] --> D
    end
    
    style D fill:#f9f,stroke:#333,stroke-width:4px
    style E fill:#ff9,stroke:#333
    style F fill:#9ff,stroke:#333
    style G fill:#f99,stroke:#333
```

## Security Configuration Structure

```mermaid
graph TD
    subgraph "Security Config"
        SC[security.yaml] --> IV[Input Validation]
        SC --> SA[Semantic Analysis]
        SC --> SAN[Sanitization]
        SC --> MON[Monitoring]
        
        IV --> ML[max_length]
        IV --> AC[allowed_chars]
        IV --> RL[rate_limit]
        
        SA --> CT[confidence_threshold]
        SA --> BT[block_threshold]
        
        SAN --> UN[unicode_normalization]
        SAN --> ZW[zero_width_removal]
        
        MON --> LA[log_all]
        MON --> AT[alert_threshold]
    end