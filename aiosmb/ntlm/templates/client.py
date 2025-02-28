from aiosmb.ntlm.structures.fields import Fields
from aiosmb.ntlm.structures.negotiate_flags import NegotiateFlags
from aiosmb.ntlm.structures.version import Version, WindowsMajorVersion, WindowsMinorVersion

NTLMClientTemplates = {
		"Windows10_15063" : {
			'flags'            :  NegotiateFlags.NEGOTIATE_56|
								  NegotiateFlags.NEGOTIATE_KEY_EXCH|
								  NegotiateFlags.NEGOTIATE_128|
								  NegotiateFlags.NEGOTIATE_VERSION|
								  NegotiateFlags.NEGOTIATE_EXTENDED_SESSIONSECURITY|
								  NegotiateFlags.NEGOTIATE_ALWAYS_SIGN|
								  NegotiateFlags.NEGOTIATE_NTLM|
								  NegotiateFlags.NEGOTIATE_LM_KEY|
								  NegotiateFlags.NEGOTIATE_SIGN|
								  NegotiateFlags.REQUEST_TARGET|
								  NegotiateFlags.NTLM_NEGOTIATE_OEM|
								  NegotiateFlags.NEGOTIATE_UNICODE,
			'version'          : Version.construct(WindowsMajorVersion.WINDOWS_MAJOR_VERSION_10, minor = WindowsMinorVersion.WINDOWS_MINOR_VERSION_0, build = 15063 ),
			'domain_name'      : None,
			'workstation_name' : None,
			'ntlm_downgrade'   : False,
		},
		"Windows10_15063_knowkey" : {
			'flags'            :  NegotiateFlags.NEGOTIATE_56|
								  NegotiateFlags.NEGOTIATE_KEY_EXCH|
								  NegotiateFlags.NEGOTIATE_128|
								  NegotiateFlags.NEGOTIATE_VERSION|
								  NegotiateFlags.NEGOTIATE_EXTENDED_SESSIONSECURITY|
								  NegotiateFlags.NEGOTIATE_ALWAYS_SIGN|
								  NegotiateFlags.NEGOTIATE_NTLM|
								  NegotiateFlags.NEGOTIATE_LM_KEY|
								  NegotiateFlags.NEGOTIATE_SIGN|
								  NegotiateFlags.REQUEST_TARGET|
								  NegotiateFlags.NTLM_NEGOTIATE_OEM|
								  NegotiateFlags.NEGOTIATE_UNICODE,
			'version'          : Version.construct(WindowsMajorVersion.WINDOWS_MAJOR_VERSION_10, minor = WindowsMinorVersion.WINDOWS_MINOR_VERSION_0, build = 15063 ),
			'domain_name'      : None,
			'workstation_name' : None,
			'ntlm_downgrade'   : False,
			'session_key'      : b'A'*16,
		},
		"Windows10_15063_nosign" : {
			'flags'            :  NegotiateFlags.NEGOTIATE_56|
								  NegotiateFlags.NEGOTIATE_KEY_EXCH|
								  NegotiateFlags.NEGOTIATE_128|
								  NegotiateFlags.NEGOTIATE_VERSION|
								  NegotiateFlags.NEGOTIATE_EXTENDED_SESSIONSECURITY|
								  NegotiateFlags.NEGOTIATE_NTLM|
								  NegotiateFlags.NEGOTIATE_LM_KEY|
								  NegotiateFlags.REQUEST_TARGET|
								  NegotiateFlags.NTLM_NEGOTIATE_OEM|
								  NegotiateFlags.NEGOTIATE_UNICODE,
			'version'          : Version.construct(WindowsMajorVersion.WINDOWS_MAJOR_VERSION_10, minor = WindowsMinorVersion.WINDOWS_MINOR_VERSION_0, build = 15063 ),
			'domain_name'      : None,
			'workstation_name' : None,
			'ntlm_downgrade'   : False,
		},
}