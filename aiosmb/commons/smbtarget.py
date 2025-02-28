import ipaddress

class SMBTarget:
	def __init__(self):
		self.ip = None
		self.port = 445
		self.hostname = None
		self.timeout = 1
		self.dc_ip = None
		self.domain = None
		
	def to_target_string(self):
		return 'cifs/%s@%s' % (self.hostname, self.domain)
	
	@staticmethod
	def from_connection_string(s):
		port = 445
		dc = None
		
		t, target = s.rsplit('@', 1)
		if target.find('/') != -1:
			target, dc = target.split('/')
			
		if target.find(':') != -1:
			target, port = target.split(':')
			
		st = SMBTarget()
		st.port = port
		st.dc_ip = dc
		st.domain, t = s.split('/', 1)
		
		try:
			st.ip = str(ipaddress.ip_address(target))
		except:
			st.hostname = target
	
		return st
		
	def get_ip(self):
		if not self.ip and not self.hostname:
			raise Exception('SMBTarget must have ip or hostname defined!')
		return self.ip if self.ip is not None else self.hostname
		
	def get_hostname(self):
		raise Exception('Not implemented!')
	
	def get_hostname_or_ip(self):
		if self.hostname:
			return self.hostname
		return self.ip
	
	def get_port(self):
		return self.port
		
	def __str__(self):
		t = '==== SMBTarget ====\r\n'
		for k in self.__dict__:
			t += '%s: %s\r\n' % (k, self.__dict__[k])
			
		return t
		
		
def test():
	s = 'TEST/victim/ntlm/nt:AAAAAAAA@10.10.10.2:445'
	creds = SMBTarget.from_connection_string(s)
	print(str(creds))
	
	s = 'TEST/victim/sspi@10.10.10.2:445/aaaa'
	creds = SMBTarget.from_connection_string(s)
	
	print(str(creds))
	
if __name__ == '__main__':
	test()