import pika
import frappe
import threading
from queue import Queue, Empty
from typing import Any, NoReturn


class RabbitMQ:
	def __init__(
		self,
		host: str = "localhost",
		port: int = 5672,
		virtual_host: str = "/",
		username: str | None = None,
		password: str | None = None,
	) -> None:
		"""Initializes the RabbitMQ object with the given parameters."""

		self.__host = host
		self.__port = port
		self.__virtual_host = virtual_host
		self.__username = username
		self.__password = password

		self._connection = None
		self._channel = None

	def _connect(self) -> None:
		"""Establishes the RabbitMQ connection and channel."""

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

	def _ensure_connection_and_channel(self) -> None:
		"""Ensures the connection and channel are open. Reopens them if necessary."""

		if not self._connection or self._connection.is_closed:
			self._connect()
		elif not self._channel or self._channel.is_closed:
			self._channel = self._connection.channel()

	def declare_queue(
		self, queue: str, max_priority: int = 0, durable: bool = True
	) -> None:
		"""Declares a queue with the given name and arguments."""

		self._ensure_connection_and_channel()

		if max_priority > 0:
			self._channel.queue_declare(
				queue=queue, arguments={"x-max-priority": max_priority}, durable=durable
			)
		else:
			self._channel.queue_declare(queue=queue, durable=durable)

	def publish(
		self,
		routing_key: str,
		body: str,
		exchange: str = "",
		priority: int = 0,
		persistent: bool = True,
	) -> None:
		"""Publishes a message to the exchange with the given routing key."""

		self._ensure_connection_and_channel()

		properties = pika.BasicProperties(
			delivery_mode=pika.DeliveryMode.Persistent if persistent else None,
			priority=priority if priority > 0 else None,
		)
		self._channel.basic_publish(
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
	) -> NoReturn:
		"""Consumes messages from the queue with the given callback."""

		self._ensure_connection_and_channel()

		if prefetch_count > 0:
			self._channel.basic_qos(prefetch_count=prefetch_count)

		self._channel.basic_consume(
			queue=queue, on_message_callback=callback, auto_ack=auto_ack
		)
		self._channel.start_consuming()

	def basic_get(
		self,
		queue: str,
		auto_ack: bool = False,
	) -> tuple[Any, int, bytes] | None:
		"""Gets a message from the queue and returns it."""

		self._ensure_connection_and_channel()
		method, properties, body = self._channel.basic_get(queue=queue, auto_ack=auto_ack)

		if method:
			return method, properties, body

		return None

	def _disconnect(self) -> None:
		"""Disconnects from the RabbitMQ server."""

		if self._connection and self._connection.is_open:
			self._connection.close()


class RabbitMQConnectionPool:
	def __init__(self, initial_pool_size: int = 1, max_pool_size: int = 10) -> None:
		"""Initializes the RabbitMQ connection pool with the given parameters."""

		self.pool = Queue(maxsize=max_pool_size)
		self.lock = threading.Lock()
		self.max_pool_size = max_pool_size
		self._initialize_pool(initial_pool_size)

	def _initialize_pool(self, size: int) -> None:
		"""Initializes the pool with RabbitMQ connections."""

		for x in range(size):
			connection = self._create_new_connection()
			self.pool.put(connection)

	def _create_new_connection(self) -> RabbitMQ:
		"""Creates a new RabbitMQ connection."""

		mail_settings = frappe.get_cached_doc("Mail Settings")
		return RabbitMQ(
			host=mail_settings.rmq_host,
			port=mail_settings.rmq_port,
			virtual_host=mail_settings.rmq_virtual_host,
			username=mail_settings.rmq_username,
			password=mail_settings.get_password("rmq_password")
			if mail_settings.rmq_password
			else None,
		)

	def get_connection(self) -> RabbitMQ:
		"""Gets a connection from the pool, creating a new one if necessary."""

		with self.lock:
			if self.pool.empty() and self.pool.qsize() < self.max_pool_size:
				# Create new connection if the pool is empty and hasn't reached max size
				self._initialize_pool(1)

			try:
				return self.pool.get(timeout=5)
			except Empty:
				raise RuntimeError("No connections available in the pool.")

	def return_connection(self, connection: RabbitMQ) -> None:
		"""Returns a connection to the pool."""

		with self.lock:
			if self.pool.qsize() < self.max_pool_size:
				self.pool.put(connection)
			else:
				connection._disconnect()  # Close connection if pool is full


class RabbitMQConnectionContext:
	def __init__(self, pool: RabbitMQConnectionPool) -> None:
		"""Initializes the RabbitMQ connection context manager with the given pool."""

		self.pool = pool
		self.connection: RabbitMQ | None = None

	def __enter__(self) -> RabbitMQ:
		"""Returns a RabbitMQ connection from the pool."""

		self.connection = self.pool.get_connection()
		return self.connection

	def __exit__(self, exc_type, exc_val, exc_tb) -> None:
		"""Returns the RabbitMQ connection to the pool."""

		if self.connection:
			self.pool.return_connection(self.connection)
			self.connection = None


def rabbitmq_context() -> RabbitMQConnectionContext:
	"""Returns a RabbitMQ connection context manager."""

	global connection_pool
	return RabbitMQConnectionContext(pool=connection_pool)


connection_pool = RabbitMQConnectionPool()
