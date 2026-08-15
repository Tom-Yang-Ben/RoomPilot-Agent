"""Typed failures shared by the Django RAG runtime and Bella's HTTP adapter."""


class RagError(RuntimeError):
    code = "rag_error"


class RagDisabledError(RagError):
    code = "rag_disabled"


class RagDependencyError(RagError):
    code = "rag_dependency_unavailable"


class RagDatabaseError(RagError):
    code = "rag_database_unavailable"


class RagUpstreamError(RagError):
    code = "rag_parser_unavailable"
