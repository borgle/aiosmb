
import logging
from aiosmb import logger

#from aiosmb.dtyp.constrcuted_security.guid import GUID
from aiosmb.commons.smbcontainer import SMBUserSecrets
from aiosmb.dtyp.structures.filetime import FILETIME
from aiosmb.dtyp.constrcuted_security.sid import SID
from aiosmb.dcerpc.v5.dtypes import NULL
from aiosmb.dcerpc.v5.uuid import string_to_bin
from aiosmb.dcerpc.v5.transport.smbtransport import SMBTransport
from aiosmb.dcerpc.v5.transport.factory import DCERPCTransportFactory
from aiosmb.dcerpc.v5 import epm, drsuapi, samr
from aiosmb.dcerpc.v5.interfaces.servicemanager import *
from aiosmb.dcerpc.v5.rpcrt import RPC_C_AUTHN_LEVEL_PKT_INTEGRITY, RPC_C_AUTHN_LEVEL_PKT_PRIVACY, DCERPCException, RPC_C_AUTHN_GSS_NEGOTIATE
		
class SMBDRSUAPI:
	def __init__(self, connection, domainname = None):
		self.connection = connection	
		self.domainname = domainname
		
		self.dce = None
		self.handle = None
		
		self.__NtdsDsaObjectGuid = None
		self.__ppartialAttrSet = None
		
		self.ATTRTYP_TO_ATTID = {
				'userPrincipalName': '1.2.840.113556.1.4.656',
				'sAMAccountName': '1.2.840.113556.1.4.221',
				'unicodePwd': '1.2.840.113556.1.4.90',
				'dBCSPwd': '1.2.840.113556.1.4.55',
				'ntPwdHistory': '1.2.840.113556.1.4.94',
				'lmPwdHistory': '1.2.840.113556.1.4.160',
				'supplementalCredentials': '1.2.840.113556.1.4.125',
				'objectSid': '1.2.840.113556.1.4.146',
				'pwdLastSet': '1.2.840.113556.1.4.96',
				'userAccountControl':'1.2.840.113556.1.4.8',
			}
			
		self.NAME_TO_ATTRTYP = {
			'userPrincipalName': 0x90290,
			'sAMAccountName': 0x900DD,
			'unicodePwd': 0x9005A,
			'dBCSPwd': 0x90037,
			'ntPwdHistory': 0x9005E,
			'lmPwdHistory': 0x900A0,
			'supplementalCredentials': 0x9007D,
			'objectSid': 0x90092,
			'userAccountControl':0x90008,
		}
		
		self.KERBEROS_TYPE = {
			1:'dec-cbc-crc',
			3:'des-cbc-md5',
			17:'aes128-cts-hmac-sha1-96',
			18:'aes256-cts-hmac-sha1-96',
			0xffffff74:'rc4_hmac',
		}
		
	async def __aenter__(self):
		return self
		
	async def __aexit__(self, exc_type, exc, traceback):
		await self.close()
		
	async def connect(self, open = False):
		stringBinding = await epm.hept_map(self.connection, drsuapi.MSRPC_UUID_DRSUAPI, protocol='ncacn_ip_tcp')
		#print(stringBinding)
		rpc = DCERPCTransportFactory(stringBinding, self.connection)
		
		rpc.setRemoteHost(self.connection.target.get_ip())
		rpc.setRemoteName(self.connection.target.get_ip())
		
		self.dce = rpc.get_dce_rpc()
		#the line below must be set!
		self.dce.set_auth_level(RPC_C_AUTHN_LEVEL_PKT_PRIVACY)
		
		try:
			await self.dce.connect()
		except  Exception as e:
			print(e)
			
		if open == True:
			await self.open()
			
	async def open(self):
		if not self.dce:
			await self.connect()
		
		try:
			await self.dce.bind(drsuapi.MSRPC_UUID_DRSUAPI)
		except Exception as e:
			print('!!!!!!!!!!!!!! Exc! %s' % e)
		request = drsuapi.DRSBind()
		request['puuidClientDsa'] = drsuapi.NTDSAPI_CLIENT_GUID
		drs = drsuapi.DRS_EXTENSIONS_INT()
		drs['cb'] = len(drs) #- 4
		drs['dwFlags'] = drsuapi.DRS_EXT_GETCHGREQ_V6 | drsuapi.DRS_EXT_GETCHGREPLY_V6 | drsuapi.DRS_EXT_GETCHGREQ_V8 | \
						 drsuapi.DRS_EXT_STRONG_ENCRYPTION
		drs['SiteObjGuid'] = drsuapi.NULLGUID
		drs['Pid'] = 0
		drs['dwReplEpoch'] = 0
		drs['dwFlagsExt'] = 0
		drs['ConfigObjGUID'] = drsuapi.NULLGUID
		# I'm uber potential (c) Ben
		drs['dwExtCaps'] = 0xffffffff
		request['pextClient']['cb'] = len(drs)
		request['pextClient']['rgb'] = list(drs.getData())
		resp = await self.dce.request(request)
		
		# Let's dig into the answer to check the dwReplEpoch. This field should match the one we send as part of
		# DRSBind's DRS_EXTENSIONS_INT(). If not, it will fail later when trying to sync data.
		drsExtensionsInt = drsuapi.DRS_EXTENSIONS_INT()

		# If dwExtCaps is not included in the answer, let's just add it so we can unpack DRS_EXTENSIONS_INT right.
		ppextServer = b''.join(resp['ppextServer']['rgb']) + b'\x00' * (
		len(drsuapi.DRS_EXTENSIONS_INT()) - resp['ppextServer']['cb'])
		drsExtensionsInt.fromString(ppextServer)

		if drsExtensionsInt['dwReplEpoch'] != 0:
			# Different epoch, we have to call DRSBind again
			if logger.level == logging.DEBUG:
				logger.debug("DC's dwReplEpoch != 0, setting it to %d and calling DRSBind again" % drsExtensionsInt[
					'dwReplEpoch'])
			drs['dwReplEpoch'] = drsExtensionsInt['dwReplEpoch']
			request['pextClient']['cb'] = len(drs)
			request['pextClient']['rgb'] = list(drs.getData())
			resp = await self.dce.request(request)

		self.handle = resp['phDrs']

		# Now let's get the NtdsDsaObjectGuid UUID to use when querying NCChanges
		resp = await drsuapi.hDRSDomainControllerInfo(self.dce, self.handle, self.domainname, 2)
		if logger.level == logging.DEBUG:
			logger.debug('DRSDomainControllerInfo() answer %s' % resp.dump())

		if resp['pmsgOut']['V2']['cItems'] > 0:
			self.__NtdsDsaObjectGuid = resp['pmsgOut']['V2']['rItems'][0]['NtdsDsaObjectGuid']
		else:
			logger.error("Couldn't get DC info for domain %s" % self.domainname)
			raise Exception('Fatal, aborting!')
	
	async def get_user_secrets(self, username):
		ra = {
			'userPrincipalName': '1.2.840.113556.1.4.656',
			'sAMAccountName': '1.2.840.113556.1.4.221',
			'unicodePwd': '1.2.840.113556.1.4.90',
			'dBCSPwd': '1.2.840.113556.1.4.55',
			'ntPwdHistory': '1.2.840.113556.1.4.94',
			'lmPwdHistory': '1.2.840.113556.1.4.160',
			'supplementalCredentials': '1.2.840.113556.1.4.125',
			'objectSid': '1.2.840.113556.1.4.146',
			'pwdLastSet': '1.2.840.113556.1.4.96',
			'userAccountControl':'1.2.840.113556.1.4.8'
		}
		formatOffered = drsuapi.DS_NT4_ACCOUNT_NAME_SANS_DOMAIN
		
		crackedName = await self.DRSCrackNames(
			formatOffered,
			drsuapi.DS_NAME_FORMAT.DS_UNIQUE_ID_NAME,
			name=username
		)
		
		###### TODO: CHECKS HERE
		
		#guid = GUID.from_string(crackedName['pmsgOut']['V1']['pResult']['rItems'][0]['pName'][:-1][1:-1])
		guid = crackedName['pmsgOut']['V1']['pResult']['rItems'][0]['pName'][:-1][1:-1]
		
		userRecord = await self.DRSGetNCChanges(guid, ra)
		
		replyVersion = 'V%d' % userRecord['pdwOutVersion']
		if userRecord['pmsgOut'][replyVersion]['cNumObjects'] == 0:
			raise Exception('DRSGetNCChanges didn\'t return any object!')
		
		#print(userRecord.dump())
		#print(userRecord['pmsgOut'][replyVersion]['PrefixTableSrc']['pPrefixEntry'])
		
		record = userRecord
		prefixTable = userRecord['pmsgOut'][replyVersion]['PrefixTableSrc']['pPrefixEntry']
		##### decryption!
		logger.debug('Decrypting hash for user: %s' % record['pmsgOut'][replyVersion]['pNC']['StringName'][:-1])
		
		us = SMBUserSecrets()
		user_properties = None

		rid = int.from_bytes(record['pmsgOut'][replyVersion]['pObjects']['Entinf']['pName']['Sid'][-4:], 'little', signed = False)
		
		for attr in record['pmsgOut'][replyVersion]['pObjects']['Entinf']['AttrBlock']['pAttr']:
		
			try:
				attId = drsuapi.OidFromAttid(prefixTable, attr['attrTyp'])
				LOOKUP_TABLE = self.ATTRTYP_TO_ATTID
			except Exception as e:
				logger.error('Failed to execute OidFromAttid with error %s, fallbacking to fixed table' % e)
				logger.error('Exception', exc_info=True)
				input()
				# Fallbacking to fixed table and hope for the best
				attId = attr['attrTyp']
				LOOKUP_TABLE = self.NAME_TO_ATTRTYP
				
			if attId == LOOKUP_TABLE['dBCSPwd']:
				if attr['AttrVal']['valCount'] > 0:
					encrypteddBCSPwd = b''.join(attr['AttrVal']['pAVal'][0]['pVal'])
					encryptedLMHash = drsuapi.DecryptAttributeValue(self.dce.get_session_key(), encrypteddBCSPwd)
					us.lm_hash = drsuapi.removeDESLayer(encryptedLMHash, rid)
				else:
					us.lm_hash = bytes.fromhex('aad3b435b51404eeaad3b435b51404ee')
					
			elif attId == LOOKUP_TABLE['unicodePwd']:
				if attr['AttrVal']['valCount'] > 0:
					encryptedUnicodePwd = b''.join(attr['AttrVal']['pAVal'][0]['pVal'])
					encryptedNTHash = drsuapi.DecryptAttributeValue(self.dce.get_session_key(), encryptedUnicodePwd)
					us.nt_hash = drsuapi.removeDESLayer(encryptedNTHash, rid)
				else:
					us.nt_hash = bytes.fromhex('31d6cfe0d16ae931b73c59d7e0c089c0')
					
			elif attId == LOOKUP_TABLE['userPrincipalName']:
				if attr['AttrVal']['valCount'] > 0:
					try:
						us.domain = b''.join(attr['AttrVal']['pAVal'][0]['pVal']).decode('utf-16le').split('@')[-1]
					except:
						us.domain = None
				else:
					us.domain = None
						
			elif attId == LOOKUP_TABLE['sAMAccountName']:
				if attr['AttrVal']['valCount'] > 0:
					try:
						us.username = b''.join(attr['AttrVal']['pAVal'][0]['pVal']).decode('utf-16le')
					except Exception as e:
						logger.error('Cannot get sAMAccountName for %s' % record['pmsgOut'][replyVersion]['pNC']['StringName'][:-1])
						us.username = 'unknown'
				else:
					logger.error('Cannot get sAMAccountName for %s' % record['pmsgOut'][replyVersion]['pNC']['StringName'][:-1])
					us.username = 'unknown'
						
			elif attId == LOOKUP_TABLE['objectSid']:
				if attr['AttrVal']['valCount'] > 0:
					us.object_sid = SID.from_bytes(b''.join(attr['AttrVal']['pAVal'][0]['pVal']))
				else:
					logger.error('Cannot get objectSid for %s' % record['pmsgOut'][replyVersion]['pNC']['StringName'][:-1])
					us.object_sid = rid
			elif attId == LOOKUP_TABLE['pwdLastSet']:
				if attr['AttrVal']['valCount'] > 0:
					try:
						
						us.pwd_last_set = FILETIME.from_bytes(b''.join(attr['AttrVal']['pAVal'][0]['pVal'])).datetime.isoformat()
					except Exception as e:
						
						logger.error('Cannot get pwdLastSet for %s' % record['pmsgOut'][replyVersion]['pNC']['StringName'][:-1])
						us.pwd_last_set = None
						input(e)
						
			elif attId == LOOKUP_TABLE['userAccountControl']:
				if attr['AttrVal']['valCount'] > 0:
					us.user_account_status = int.from_bytes(b''.join(attr['AttrVal']['pAVal'][0]['pVal']), 'little', signed = False)
				else:
					us.user_account_status = None
					
			if attId == LOOKUP_TABLE['lmPwdHistory']:
				if attr['AttrVal']['valCount'] > 0:
					encryptedLMHistory = b''.join(attr['AttrVal']['pAVal'][0]['pVal'])
					tmpLMHistory = drsuapi.DecryptAttributeValue(self.dce.get_session_key(), encryptedLMHistory)
					for i in range(0, len(tmpLMHistory) // 16):
						LMHashHistory = drsuapi.removeDESLayer(tmpLMHistory[i * 16:(i + 1) * 16], rid)
						us.lm_history.append(LMHashHistory)
				else:
					logger.debug('No lmPwdHistory for user %s' % record['pmsgOut'][replyVersion]['pNC']['StringName'][:-1])
			elif attId == LOOKUP_TABLE['ntPwdHistory']:
				if attr['AttrVal']['valCount'] > 0:
					encryptedNTHistory = b''.join(attr['AttrVal']['pAVal'][0]['pVal'])
					tmpNTHistory = drsuapi.DecryptAttributeValue(self.dce.get_session_key(), encryptedNTHistory)
					for i in range(0, len(tmpNTHistory) // 16):
						NTHashHistory = drsuapi.removeDESLayer(tmpNTHistory[i * 16:(i + 1) * 16], rid)
						us.nt_history.append(NTHashHistory)
				else:
					logger.debug('No ntPwdHistory for user %s' % record['pmsgOut'][replyVersion]['pNC']['StringName'][:-1])
					
			elif attId == LOOKUP_TABLE['supplementalCredentials']:
				if attr['AttrVal']['valCount'] > 0:
					blob = b''.join(attr['AttrVal']['pAVal'][0]['pVal'])
					supplementalCredentials = drsuapi.DecryptAttributeValue(self.dce.get_session_key(), blob)
					if len(supplementalCredentials) < 24:
						supplementalCredentials = None
						
					else:
						try:
							user_properties = samr.USER_PROPERTIES(supplementalCredentials)
						except Exception as e:
							# On some old w2k3 there might be user properties that don't
							# match [MS-SAMR] structure, discarding them
							pass
			
		
		if user_properties is not None:
			propertiesData = user_properties['UserProperties']
			for propertyCount in range(user_properties['PropertyCount']):
				userProperty = samr.USER_PROPERTY(propertiesData)
				propertiesData = propertiesData[len(userProperty):]
				# For now, we will only process Newer Kerberos Keys and CLEARTEXT
				if userProperty['PropertyName'].decode('utf-16le') == 'Primary:Kerberos-Newer-Keys':
					propertyValueBuffer = bytes.fromhex(userProperty['PropertyValue'].decode())
					kerbStoredCredentialNew = samr.KERB_STORED_CREDENTIAL_NEW(propertyValueBuffer)
					data = kerbStoredCredentialNew['Buffer']
					for credential in range(kerbStoredCredentialNew['CredentialCount']):
						keyDataNew = samr.KERB_KEY_DATA_NEW(data)
						data = data[len(keyDataNew):]
						keyValue = propertyValueBuffer[keyDataNew['KeyOffset']:][:keyDataNew['KeyLength']]

						if  keyDataNew['KeyType'] in self.KERBEROS_TYPE:
							answer =  (self.KERBEROS_TYPE[keyDataNew['KeyType']],keyValue)
						else:
							answer =  (hex(keyDataNew['KeyType']),keyValue)
						# We're just storing the keys, not printing them, to make the output more readable
						# This is kind of ugly... but it's what I came up with tonight to get an ordered
						# set :P. Better ideas welcomed ;)
						us.kerberos_keys.append(answer)
				elif userProperty['PropertyName'].decode('utf-16le') == 'Primary:CLEARTEXT':
					# [MS-SAMR] 3.1.1.8.11.5 Primary:CLEARTEXT Property
					# This credential type is the cleartext password. The value format is the UTF-16 encoded cleartext password.
					try:
						answer = (userProperty['PropertyValue'].decode('utf-16le'))
					except UnicodeDecodeError:
						# This could be because we're decoding a machine password. Printing it hex
						answer = (userProperty['PropertyValue'].decode('utf-8'))

					us.cleartext_pwds.append(answer)
			
		
		return us
			
		
	async def DRSCrackNames(self, formatOffered=drsuapi.DS_NAME_FORMAT.DS_DISPLAY_NAME, formatDesired=drsuapi.DS_NAME_FORMAT.DS_FQDN_1779_NAME, name=''):
		if self.handle is None:
			await self.open()

		logger.debug('Calling DRSCrackNames for %s' % name)
		resp = await drsuapi.hDRSCrackNames(self.dce, self.handle, 0, formatOffered, formatDesired, (name,))
		return resp
		
	async def DRSGetNCChanges(self, guid, req_attributes = {}):
		if self.handle is None:
			self.open()

		logger.debug('Calling DRSGetNCChanges for %s ' % guid)
		request = drsuapi.DRSGetNCChanges()
		request['hDrs'] = self.handle
		request['dwInVersion'] = 8

		request['pmsgIn']['tag'] = 8
		request['pmsgIn']['V8']['uuidDsaObjDest'] = self.__NtdsDsaObjectGuid
		request['pmsgIn']['V8']['uuidInvocIdSrc'] = self.__NtdsDsaObjectGuid

		dsName = drsuapi.DSNAME()
		dsName['SidLen'] = 0
		dsName['Guid'] = string_to_bin(guid)#guid.to_bytes()
		dsName['Sid'] = ''
		dsName['NameLen'] = 0
		dsName['StringName'] = ('\x00')

		dsName['structLen'] = len(dsName.getData())

		request['pmsgIn']['V8']['pNC'] = dsName

		request['pmsgIn']['V8']['usnvecFrom']['usnHighObjUpdate'] = 0
		request['pmsgIn']['V8']['usnvecFrom']['usnHighPropUpdate'] = 0

		request['pmsgIn']['V8']['pUpToDateVecDest'] = NULL

		request['pmsgIn']['V8']['ulFlags'] =  drsuapi.DRS_INIT_SYNC | drsuapi.DRS_WRIT_REP
		request['pmsgIn']['V8']['cMaxObjects'] = 1
		request['pmsgIn']['V8']['cMaxBytes'] = 0
		request['pmsgIn']['V8']['ulExtendedOp'] = drsuapi.EXOP_REPL_OBJ
		if self.__ppartialAttrSet is None:
			self.__prefixTable = []
			self.__ppartialAttrSet = drsuapi.PARTIAL_ATTR_VECTOR_V1_EXT()
			self.__ppartialAttrSet['dwVersion'] = 1
			self.__ppartialAttrSet['cAttrs'] = len(req_attributes)
			for attId in list(req_attributes.values()):
				self.__ppartialAttrSet['rgPartialAttr'].append(drsuapi.MakeAttid(self.__prefixTable , attId))
		request['pmsgIn']['V8']['pPartialAttrSet'] = self.__ppartialAttrSet
		request['pmsgIn']['V8']['PrefixTableDest']['PrefixCount'] = len(self.__prefixTable)
		request['pmsgIn']['V8']['PrefixTableDest']['pPrefixEntry'] = self.__prefixTable
		request['pmsgIn']['V8']['pPartialAttrSetEx1'] = NULL

		return await self.dce.request(request)
		
	async def close(self):
		if self.handle:
			try:
				await drsuapi.hDRSUnbind(self.dce, self.handle)
			except:
				pass
		if self.dce:
			try:
				await self.dce.disconnect()
			except:
				pass