class ServiceError(Exception):
    """Base class for application errors translated by an interface adapter."""


class AuthenticationError(ServiceError):
    pass


class ConflictError(ServiceError):
    pass


class NotFoundError(ServiceError):
    pass


class NotInitializedError(ServiceError):
    pass
