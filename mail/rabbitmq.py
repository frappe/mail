import pika
from typing import Any, NoReturn


class RabbitMQ:
	def __init__(
		self,
		host: str = "localhost",
		port: int = 5672,
		username: str | None = None,
		password: str | None = None,
	) -> None:
		"""Initializes the RabbitMQ object with the given parameters."""

		self.__host = host
		self.__port = port
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
				host=self.__host, port=self.__port, credentials=credentials
			)
		else:
			parameters = pika.ConnectionParameters(host=self.__host, port=self.__port)

		self._connection = pika.BlockingConnection(parameters)
		self._channel = self._connection.channel()

	def declare_queue(
		self, queue: str, max_priority: int = 0, durable: bool = True
	) -> None:
		"""Declares a queue with the given name and arguments."""

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

		properties = {
			"delivery_mode": pika.DeliveryMode.Persistent if persistent else None,
			"priority": priority if priority > 0 else None,
		}
		self._channel.basic_publish(
			exchange=exchange,
			routing_key=routing_key,
			body=body,
			properties=pika.BasicProperties(**properties),
		)

	def consume(
		self,
		queue: str,
		callback: callable,
		auto_ack: bool = False,
		prefetch_count: int = 1,
	) -> NoReturn:
		"""Consumes messages from the queue with the given callback."""

		self._channel.basic_qos(prefetch_count=prefetch_count)
		self._channel.basic_consume(
			queue=queue, on_message_callback=callback, auto_ack=auto_ack
		)
		self._channel.start_consuming()

	def basic_get(
		self, queue: str, callback: callable, auto_ack: bool = False
	) -> Any | None:
		"""Gets a message from the queue and calls the callback function."""

		method, properties, body = self._channel.basic_get(queue=queue, auto_ack=auto_ack)

		if method:
			return callback(self._channel, method, properties, body)

	def _disconnect(self) -> None:
		"""Disconnects from the RabbitMQ server."""

		if self._connection and self._connection.is_open:
			self._connection.close()

	def __del__(self) -> None:
		"""Disconnects from the RabbitMQ server when the object is deleted."""

		self._disconnect()
