import enum
import asyncio

from aiosmb import logger
from aiosmb.exceptions import *

class TCPSocket:
	"""
	Generic asynchronous TCP socket class, nothing SMB related.
	Creates the connection and channels incoming/outgoing bytes via asynchonous queues.
	"""
	def __init__(self, shutdown_evt = asyncio.Event(), socket = None):
		self.settings = None
		self.socket = socket #for future, if we want a custom soscket
		self.reader = None
		self.writer = None
		
		self.out_queue = asyncio.Queue()
		self.in_queue = asyncio.Queue()
		
		self.disconnected = asyncio.Event()
		self.shutdown_evt = shutdown_evt
		
	async def disconnect(self):
		"""
		Disconnects from the socket.
		Stops the reader and writer streams.
		"""
		self.reader = None
		try:
			self.writer.close()
		except:
			pass
		self.writer = None
		self.disconnected.set()
		
	async def handle_incoming(self):
		"""
		Reads data bytes from the socket and dispatches it to the incoming queue
		"""
		while not self.disconnected.is_set() or not self.shutdown_evt.is_set():			
			data = await asyncio.gather(*[self.reader.read(4096)], return_exceptions = True)
			if isinstance(data[0], bytes):
				await self.in_queue.put(data[0])
			
			elif isinstance(data[0], asyncio.CancelledError):
				return
				
			elif isinstance(data[0], Exception):
				if not self.shutdown_evt.is_set():
					logger.exception('[TCPSocket] handle_incoming %s' % str(data[0]))
				await self.disconnect()
				return
		
	async def handle_outgoing(self):
		"""
		Reads data bytes from the outgoing queue and dispatches it to the socket
		"""
		try:
			while not self.disconnected.is_set() or not self.shutdown_evt.is_set():
				data = await self.out_queue.get()
				self.writer.write(data)
				await self.writer.drain()
		except asyncio.CancelledError:
			#the SMB connection is terminating
			return
			
		except Exception as e:
			logger.exception('[TCPSocket] handle_outgoing %s' % str(e))
			await self.disconnect()
			
		
	async def connect(self, settings):
		"""
		Main function to be called, connects to the target specified in settings, and starts reading/writing.
		"""

		self.settings = settings
		
		con = asyncio.open_connection(self.settings.get_ip(), self.settings.get_port())
		
		try:
			self.reader, self.writer = await asyncio.wait_for(con, int(self.settings.timeout))
		except asyncio.TimeoutError:
			logger.debug('[TCPSocket] Connection timeout')
			raise SMBConnectionTimeoutException() 
		except ConnectionRefusedError:
			logger.debug('[TCPSocket] Connection refused')
			raise SMBConnectionRefusedException()
		except asyncio.CancelledError:
			#the SMB connection is terminating
			return
		except Exception as e:
			logger.exception('[TCPSocket] connect generic exception')
			raise e
		
		asyncio.ensure_future(self.handle_incoming())
		asyncio.ensure_future(self.handle_outgoing())
		return

			
			