from time import strptime
from asyncua import ua
from statistics import mean
from datetime import datetime, date, timedelta


def time_calculation(previous_time):
    previous_time_object = datetime.strptime(previous_time, "%H:%M:%S").time()
    duration_object = datetime.combine(date.today(), previous_time_object) + timedelta(seconds=1)
    duration_string = duration_object.strftime("%H:%M:%S")
    return duration_string



def conn_commit(conn, sql_instruction):
    cur = conn.cursor()
    cur.execute(sql_instruction)
    conn.commit()




def create_table(conn):
    sql_create_table = """CREATE TABLE IF NOT EXISTS oee_data (
                            id integer PRIMARY KEY,
                            datetime DATETIME NOT NULL,
                            recipe string NOT NULL,
                            error_count integer NOT NULL,
                            total_pass integer NOT NULL,
                            total_fail integer NOT NULL,
                            quantity_in integer NOT NULL,
                            quantity_out integer NOT NULL,
                            total_yield float NOT NULL
                        );"""
    c = conn.cursor()
    c.execute(sql_create_table)

def ua_variant_data_type(data_type: str, data_value: any):
    """create a UA Variant object

    Args:
        data_type (string): UInt16,UInt32,UInt64,String,Boolean,Float
        data_value (any): data to be wrapped inside the UA Variant Object

    Returns:
        ua object: ua object to used when writing to client
    """
    if data_type == 'UInt16':
        return ua.Variant(int(data_value), ua.VariantType.UInt16)
    elif data_type == 'UInt32':
        return ua.Variant(int(data_value), ua.VariantType.UInt32)
    elif data_type == 'Int32':
        return ua.Variant(int(data_value), ua.VariantType.Int32)
    elif data_type == 'String':
        return ua.Variant(str(data_value), ua.VariantType.String)
    elif data_type == 'Boolean':
        return ua.Variant(bool(int(data_value)), ua.VariantType.Boolean)
    elif data_type == 'Float':
        return ua.Variant(float(data_value), ua.VariantType.Float)

def plc_write_method(start_device:str, data_value:int, data_format:str):
        """

        Args:
            start_device (str): [description]
            data_value (int): [description]
            data_format (str): [description]

        Returns:
            byte: [description]
        """
        if data_format == 'Boolean':
                return bytes(
                    f"WR {start_device} {int(data_value)}\r\n", "utf-8")
        elif data_format == 'UInt16':
                return bytes(
                    f"WR {start_device}.U {data_value}\r\n", "utf-8")
        elif data_format == 'UInt32':
                return bytes(
                    f"WR {start_device}.D {data_value}\r\n", "utf-8")
        elif data_format == 'Int32':
                return bytes(
                    f"WR {start_device}.L {data_value}\r\n", "utf-8")

def checkTableExists(conn, tablename:str):
    """function to check if table exist

    Args:
        conn (object): connection object
        tablename (string): name of table

    Returns:
        bool: returns result.
    """
    cursor = conn.cursor()
    cursor.execute(
        f"SELECT * FROM sqlite_master WHERE type='table' AND name='{tablename}';")
    table = cursor.fetchone()
    if table is not None:
        if tablename in table:
            cursor.close()
            return True
    else:
        cursor.close()
    
        return False

def signed_integer_check(new_value):
        if new_value > 2147483647:
            new_value = 2147483647
        if new_value < -2147483648:
            new_value = -2147483648
        return new_value


def get_historized_value(conn, namespace_index,node_id, data_type):
    dbcur = conn.cursor()
    dbcur.execute(f"SELECT Value FROM '{namespace_index}_{node_id}' ORDER BY _Id DESC LIMIT 1")
    previous_data = dbcur.fetchall()
    dbcur.close()
    previous_value = previous_data[0][0]
    initial_value = data_type_conversion(data_type, previous_value)
    return initial_value

def plc_read_method(start_device, number_of_device, data_format):
        if data_format == 'Boolean':
                return bytes(
                    f"RDS {start_device} {number_of_device}\r\n", "utf-8")
        elif data_format ==  'UInt16':
                return bytes(
                    f"RDS {start_device}.U {number_of_device}\r\n", "utf-8")
        elif data_format == 'UInt32':
                return bytes(
                    f"RDS {start_device}.D {number_of_device}\r\n", "utf-8")
        elif data_format == 'Int32':
                return bytes(
                    f"RDS {start_device}.L {number_of_device}\r\n", "utf-8")

def data_type_conversion(data_type, data_value):
    """convert data types, to safeguard I/O operation

    Args:
        data_type (string): [description]
        data_value (any): [description]

    Returns:
        [type]: [description]
    """
    if data_type == 'UInt16':
        return int(data_value)
    if data_type == 'UInt32':
        return int(data_value)
    if data_type == 'Int32':
        return int(data_value)
    if data_type == 'UInt64':    
        return int(data_value)
    if data_type == 'String':
        return str(data_value)
    if data_type == 'Boolean':
        return bool(data_value)
    if data_type == 'Float':
        return float(data_value)

def byte_swap_method(int_str):
    
    runner_count = format(int_str, 'x')
    if len(runner_count) > 1:
        s1 = runner_count[:len(runner_count)//2]
        s2 = runner_count[len(runner_count)//2:]
        runner_count_str = bytes.fromhex(s2+s1).decode('utf-8')
    else:
        runner_count_str = '0'
    return runner_count_str

def str_to_list(label_string):
        if isinstance(label_string, str):
            if ',' in label_string:
                monitored_node = label_string.split(',')
                if monitored_node[0].isdigit():
                    monitored_node_map = map(int, monitored_node)
                    monitored_node = list(monitored_node_map)
                else:
                    monitored_node = [items.strip() for items in monitored_node]
            elif "None" not in label_string:
                monitored_node = [label_string]
            else:
                monitored_node = ["None"]
        elif isinstance(label_string, float):
            monitored_node = [int(label_string)]


        return monitored_node

def month_str(month):
    if month > 10:
        month = month + 54
        month_str = chr(month)
        return month_str
    elif month== 10:
        month = str(0)    
    return month

def uph_calculation(uph_minute_interval, number_to_append):
    uph_minute_interval.append(number_to_append)
    uph_minute_interval.pop(0)
    if uph_minute_interval[0] == 0:
        uph_minute = 0
    else:
        uph_minute = (
            uph_minute_interval[1]-uph_minute_interval[0])*60
        if uph_minute < 0:
            uph_minute = 0 #this is to ensure that after oee reset happens, no negative UPH.
    return uph_minute_interval, uph_minute


def uph_array_calculation(minute_interval_array):
    try:
        average_uph = mean(minute_interval_array)#sum(self.uph_array) // len(self.uph_array)
        average_uph = round(average_uph)
    except:
        average_uph = 0
    return average_uph