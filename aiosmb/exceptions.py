
class SMBException(Exception):
	def __init__(self, message = '', ntstatus = None):
		super().__init__(message)
		self.ntstatus = ntstatus
		
class SMBConnectionTimeoutException(SMBException):
	pass
	
class SMBConnectionRefusedException(SMBException):
	pass
	
class SMBUnsupportedDialectSelected(SMBException):
	pass

class SMBUnsupportedDialectSign(SMBException):
	pass
	
class SMBUnsupportedSMBVersion(SMBException):
	pass
	
class SMBKerberosPreauthFailed(SMBException):
	pass

class SMBAuthenticationFailed(SMBException):
	pass
	
class SMBGenericException(SMBException):
	pass
	
class SMBIncorrectShareName(SMBException):
	pass
	
class SMBCreateAccessDenied(SMBException):
	pass