from data_handler import plc_read_method, plc_write_method

async def plc_tcp_socket_write_request(start_device: str, data_value: int, data_format: str, reader, writer):
    """[summary]

    Args:
        start_device (str): lead PLC address
        data_value (int): data to write at lead PLC address
        data_format (str): data format of the data writing
        reader (object): reader object
        writer (object): writer object
    """
    encapsulate = plc_write_method(
        start_device, data_value, data_format)
    writer.write(encapsulate)
    await writer.drain()
    await reader.readuntil(separator=b'\r\n')

async def plc_tcp_socket_read_request(start_device: str, number_of_device: int, data_format: str, reader, writer):
    encapsulate = plc_read_method(
        start_device, number_of_device, data_format)
    writer.write(encapsulate)
    await writer.drain()
    recv_value_byte = await reader.readuntil(separator=b'\r\n')
    recv_value_decoded = recv_value_byte.decode("UTF-8")
    recv_value_strip = recv_value_decoded.rstrip()
    recv_value = recv_value_strip.split(" ")
    return recv_value
