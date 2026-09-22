"""Canonical skill vocabulary shared by resume parsing and job-description matching.

Each canonical name maps to the aliases recruiters and candidates actually write.
Matching is case-insensitive on word boundaries, so "React" does not match "reactive".
"""

import re
from typing import Dict, List, Pattern, Tuple

SKILLS: Dict[str, List[str]] = {
    # Languages
    "Python": ["python"],
    "JavaScript": ["javascript", "js", "ecmascript"],
    "TypeScript": ["typescript", "ts"],
    "Java": ["java"],
    "Kotlin": ["kotlin"],
    "Scala": ["scala"],
    "Go": ["go", "golang"],
    "Rust": ["rust"],
    "C++": ["c++", "cpp"],
    "C#": ["c#", "csharp"],
    "C": ["c"],
    "Ruby": ["ruby"],
    "PHP": ["php"],
    "Swift": ["swift"],
    "Objective-C": ["objective-c"],
    "Elixir": ["elixir"],
    "R": ["r"],
    "SQL": ["sql"],
    "Bash": ["bash", "shell scripting"],
    # Frontend
    "React": ["react", "react.js", "reactjs"],
    "Next.js": ["next.js", "nextjs"],
    "Vue": ["vue", "vue.js", "vuejs"],
    "Angular": ["angular"],
    "Svelte": ["svelte"],
    "HTML": ["html", "html5"],
    "CSS": ["css", "css3"],
    "Tailwind CSS": ["tailwind", "tailwind css", "tailwindcss"],
    "Redux": ["redux"],
    "React Native": ["react native"],
    "Flutter": ["flutter"],
    "iOS": ["ios"],
    "Android": ["android"],
    # Backend & frameworks
    "Node.js": ["node.js", "nodejs", "node"],
    "Express": ["express", "express.js"],
    "NestJS": ["nestjs", "nest.js"],
    "Django": ["django"],
    "Flask": ["flask"],
    "FastAPI": ["fastapi"],
    "Spring": ["spring", "spring boot", "springboot"],
    "Rails": ["rails", "ruby on rails"],
    ".NET": [".net", "dotnet", "asp.net"],
    "GraphQL": ["graphql"],
    "REST APIs": ["rest", "rest api", "rest apis", "restful"],
    "gRPC": ["grpc"],
    "Microservices": ["microservices", "microservice"],
    "Distributed Systems": ["distributed systems", "distributed system"],
    "System Design": ["system design", "systems design"],
    "API Design": ["api design"],
    "Celery": ["celery"],
    # Data stores & streaming
    "PostgreSQL": ["postgresql", "postgres", "psql"],
    "MySQL": ["mysql"],
    "MongoDB": ["mongodb", "mongo"],
    "Redis": ["redis"],
    "Elasticsearch": ["elasticsearch", "opensearch"],
    "DynamoDB": ["dynamodb"],
    "Cassandra": ["cassandra"],
    "Kafka": ["kafka"],
    "RabbitMQ": ["rabbitmq"],
    "Snowflake": ["snowflake"],
    "BigQuery": ["bigquery"],
    "Spark": ["spark", "pyspark", "apache spark"],
    "Airflow": ["airflow"],
    "dbt": ["dbt"],
    "Database Design": ["database design", "data modeling", "data modelling"],
    "Data Pipelines": ["data pipelines", "data pipeline", "etl", "elt"],
    "Data Warehousing": ["data warehouse", "data warehousing"],
    # Cloud & infra
    "AWS": ["aws", "amazon web services"],
    "GCP": ["gcp", "google cloud"],
    "Azure": ["azure"],
    "Docker": ["docker", "containers", "containerization"],
    "Kubernetes": ["kubernetes", "k8s"],
    "Terraform": ["terraform"],
    "CI/CD": ["ci/cd", "cicd", "continuous integration", "continuous delivery"],
    "GitHub Actions": ["github actions"],
    "Linux": ["linux", "unix"],
    "Observability": ["observability", "prometheus", "grafana", "datadog", "opentelemetry"],
    "Security": ["application security", "appsec", "security engineering"],
    "Networking": ["networking", "tcp/ip"],
    "Serverless": ["serverless", "lambda"],
    # AI / ML
    "Machine Learning": ["machine learning", "ml"],
    "Deep Learning": ["deep learning"],
    "PyTorch": ["pytorch"],
    "TensorFlow": ["tensorflow"],
    "LLMs": ["llm", "llms", "large language models", "large language model", "genai", "generative ai"],
    "NLP": ["nlp", "natural language processing"],
    "Computer Vision": ["computer vision"],
    "RAG": ["rag", "retrieval augmented generation", "retrieval-augmented generation"],
    "Evaluation": ["evals", "model evaluation", "llm evaluation"],
    "MLOps": ["mlops"],
    "Feature Stores": ["feature store", "feature stores"],
    "Statistics": ["statistics", "statistical"],
    "Pandas": ["pandas"],
    # Practices
    "Git": ["git"],
    "TDD": ["tdd", "test-driven development", "test driven development"],
    "Testing": ["unit testing", "integration testing", "automated testing", "test automation"],
    "Agile": ["agile", "scrum", "kanban"],
    "Performance": ["performance optimization", "performance tuning", "performance engineering"],
    "Performance Profiling": ["profiling"],
    # Product & leadership
    "Product Strategy": ["product strategy"],
    "User Research": ["user research"],
    "Analytics": ["analytics", "product analytics"],
    "Stakeholder Management": ["stakeholder management"],
    "Roadmap Planning": ["roadmap", "roadmapping", "roadmap planning"],
    "People Leadership": ["people management", "people leadership", "managing engineers", "line management"],
    "Hiring": ["hiring engineers", "recruiting engineers", "building teams", "team building"],
    "Mentorship": ["mentorship", "mentoring", "coaching"],
    "Budgeting": ["budgeting", "budget ownership"],
    "ML Strategy": ["ml strategy", "ai strategy"],
    "Pipelines": ["pipelines"],
    "Warehousing": ["warehousing"],
}

# Aliases too ambiguous to trust in free text unless written exactly like the canonical name.
_CASE_SENSITIVE = {"go": "Go", "c": "C", "r": "R", "ts": "TS", "ml": "ML", "rest": "REST", "node": "Node"}


def _pattern(alias: str) -> Pattern[str]:
    if alias in _CASE_SENSITIVE:
        # Short words: exact case, and not "R&D" / "Go-to-market" / "go to".
        text = re.escape(_CASE_SENSITIVE[alias])
        return re.compile(rf"(?<![\w+#.&-]){text}(?![\w+#&-]|\.\w|\s+to\b)")
    return re.compile(rf"(?<![\w+#.]){re.escape(alias)}(?![\w+#]|\.\w)", re.IGNORECASE)


_COMPILED: List[Tuple[str, List[Pattern[str]]]] = [
    (name, [_pattern(a) for a in aliases]) for name, aliases in SKILLS.items()
]


def find_skills(text: str) -> List[str]:
    """Canonical skills mentioned in `text`, in vocabulary order."""
    return [name for name, patterns in _COMPILED if any(p.search(text) for p in patterns)]
