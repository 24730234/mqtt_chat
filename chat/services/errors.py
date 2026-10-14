class ServiceError(Exception):
    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409


class PreconditionFailed(ServiceError):
    status_code = 412


class PreconditionRequired(ServiceError):
    status_code = 428


class AuthenticationError(ServiceError):
    status_code = 401


class PermissionError(ServiceError):
    status_code = 403
