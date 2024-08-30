import pika
import frappe
import threading
from queue import Queue
from contextlib import contextmanager
from typing import Any, Generator, TYPE_CHECKING

if TYPE_CHECKING:
	from pika import BlockingConnection
	from pika.adapters.blocking_connection import BlockingChannel


class RabbitMQ:
	def __init__(
		self,
		host: str = "localhost",
		port: int = 5672,
		virtual_host: str = "/",
		username: str | None = None,
		password: str | None = None,
	) -> None:
		"""Initializes the RabbitMQ connection with the given parameters."""

		self.__host = host
		self.__port = port
		self.__virtual_host = virtual_host
		self.__username = username
		self.__password = password

		self._connection = None
		self._channel = None
		self._connect()

	def _connect(self) -> None:
		"""Connects to the RabbitMQ server."""

		if self.__username and self.__password:
			credentials = pika.PlainCredentials(self.__username, self.__password)
			parameters = pika.ConnectionParameters(
				host=self.__host,
				port=self.__port,
				virtual_host=self.__virtual_host,
				credentials=credentials,
			)
		else:
			parameters = pika.ConnectionParameters(
				host=self.__host, port=self.__port, virtual_host=self.__virtual_host
			)

		self._connection = pika.BlockingConnection(parameters)
		self._channel = self._connection.channel()

	@property
	def connection(self) -> "BlockingConnection":
		"""Returns the connection to the RabbitMQ server."""

		if not self._connection or self._connection.is_closed:
			self._connect()

		return self._connection

	@property
	def channel(self) -> "BlockingChannel":
		"""Returns the channel to the RabbitMQ server."""

		if not self._channel or self._channel.is_closed:
			self._channel = self._connection.channel()

		return self._channel

	def declare_queue(
		self, queue: str, max_priority: int = 0, durable: bool = True
	) -> None:
		"""Declares a queue with the given name and arguments."""

		arguments = {"x-max-priority": max_priority} if max_priority > 0 else None
		self.channel.queue_declare(queue=queue, arguments=arguments, durable=durable)

	def publish(
		self,
		routing_key: str,
		body: str,
		exchange: str = "",
		priority: int = 0,
		persistent: bool = True,
	) -> None:
		"""Publishes a message to the exchange with the given routing key."""

		properties = pika.BasicProperties(
			delivery_mode=pika.DeliveryMode.Persistent if persistent else None,
			priority=priority if priority > 0 else None,
		)
		self.channel.basic_publish(
			exchange=exchange,
			routing_key=routing_key,
			body=body,
			properties=properties,
		)

	def consume(
		self,
		queue: str,
		callback: callable,
		auto_ack: bool = False,
		prefetch_count: int = 0,
	) -> None:
		"""Consumes messages from the queue with the given callback."""

		if prefetch_count > 0:
			self.channel.basic_qos(prefetch_count=prefetch_count)

		self.channel.basic_consume(
			queue=queue, on_message_callback=callback, auto_ack=auto_ack
		)
		self.channel.start_consuming()

	def basic_get(
		self,
		queue: str,
		auto_ack: bool = False,
	) -> tuple[Any, int, bytes] | None:
		"""Gets a message from the queue and returns it."""

		method, properties, body = self.channel.basic_get(queue=queue, auto_ack=auto_ack)

		if method:
			return method, properties, body

		return None

	def _disconnect(self) -> None:
		"""Disconnects from the RabbitMQ server."""

		if self._connection and self._connection.is_open:
			self._connection.close()


class RabbitMQConnectionPool:
	_instance = None

	def __new__(cls, *args, **kwargs) -> "RabbitMQConnectionPool":
		"""Singleton pattern to ensure only one instance of the class is created."""

		if not cls._instance:
			cls._instance = super(RabbitMQConnectionPool, cls).__new__(cls)

		return cls._instance

	def __init__(
		self,
		host: str = "localhost",
		port: int = 5672,
		virtual_host: str = "/",
		username: str | None = None,
		password: str | None = None,
		pool_size: int = 5,
	) -> None:
		"""Initializes the RabbitMQ connection pool."""

		if not hasattr(self, "_initialized"):  # Ensure __init__ is run only once
			self.__host = host
			self.__port = port
			self.__virtual_host = virtual_host
			self.__username = username
			self.__password = password

			self._lock = threading.Lock()
			self._condition = threading.Condition(self._lock)
			self._pool_size = pool_size
			self._pool = Queue(maxsize=pool_size)
			self._initialized = True

	def _create_new_connection(self) -> RabbitMQ:
		"""Creates a new RabbitMQ connection."""

		return RabbitMQ(
			host=self.__host,
			port=self.__port,
			virtual_host=self.__virtual_host,
			username=self.__username,
			password=self.__password,
		)

	def get_connection(self) -> RabbitMQ:
		"""Returns a RabbitMQ connection from the pool."""

		with self._condition:
			while self._pool.empty():
				if self._pool.qsize() < self._pool_size:
					return self._create_new_connection()
				if not self._condition.wait(timeout=5):
					raise RuntimeError("No connections available in the pool.")

			return self._pool.get()

	def return_connection(self, connection: RabbitMQ) -> None:
		"""Return an RabbitMQ connection to the pool."""

		with self._condition:
			if self._pool.full():
				connection._disconnect()
			else:
				self._pool.put(connection)
				self._condition.notify()

	def close_connections(self) -> None:
		"""Close all RabbitMQ connections in the pool."""

		with self._condition:
			while not self._pool.empty():
				connection: RabbitMQ = self._pool.get()
				connection._disconnect()

			self._condition.notify_all()


@contextmanager
def rabbitmq_context() -> Generator[RabbitMQ, None, None]:
	"""Context manager to get a RabbitMQ connection from the pool."""

	mail_settings = frappe.get_cached_doc("Mail Settings")
	pool = RabbitMQConnectionPool(
		host=mail_settings.rmq_host,
		port=mail_settings.rmq_port,
		virtual_host=mail_settings.rmq_virtual_host,
		username=mail_settings.rmq_username,
		password=mail_settings.get_password("rmq_password")
		if mail_settings.rmq_password
		else None,
	)
	connection: RabbitMQ | None = None

	try:
		connection = pool.get_connection()
		yield connection
	finally:
		if connection:
			pool.return_connection(connection)
