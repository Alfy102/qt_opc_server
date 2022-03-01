import asyncio
from os.path import join
from datetime import datetime
from xmlrpc.client import Server
from asyncua.server.history_sql import HistorySQLite
import sqlite3
from data_handler import (
    ua_variant_data_type,
    checkTableExists,
    get_historized_value
    )
from subscriptions import (
    SubEncoderHandler,
    SubHmiHandler,
    SubIDTrackHandler,
    SubMonitoredNodes,
    SubInputLabelHandler,
    SubOutputLabelHandler,
    SubModuleStatusHandler,
    SubMachineStatusHandler,
    SubDeviceStatusHandler,
    SubWPValidationHandler,
    SubAlarmHandler
)
from server_time_handler import (
    SubSecondsHandler,
    SubMinutesHandler,
    SubHoursHandler,
    SubDaysHandler,
    SubMonthsHandler,
    SubYearsHandler
)
from configparser import ConfigParser
from plc_comm import plc_tcp_socket_read_request, plc_tcp_socket_write_request
from opc_server_class import OpcServerClass as opc_server

from queue import Queue
from PyQt6.QtCore import QObject, pyqtSignal

class OpcServerThread(QObject, opc_server):
    initialize_ui_label = pyqtSignal()
    id_track_signal = pyqtSignal(int, int)
    uph_update_signal = pyqtSignal()
    alarm_signal = pyqtSignal(int, int)
    machine_status_signal = pyqtSignal()#int, int)
    oee_time_signal = pyqtSignal(int, str)
    label_update_signal = pyqtSignal(list, str)
    input_relay_signal = pyqtSignal(int, int)
    output_relay_signal = pyqtSignal(int, int)
    encoder_pos_signal = pyqtSignal(int)
    seconds_signal = pyqtSignal(int)
    minutes_signal = pyqtSignal(int)
    hours_signal = pyqtSignal(int)
    days_signal = pyqtSignal(int)
    months_signal = pyqtSignal(int)
    years_signal = pyqtSignal(int)
    reset_lot_oee_signal = pyqtSignal()
    device_status_signal = pyqtSignal(int, int)
    module_status_signal = pyqtSignal(int, int)
    def __init__(self, current_file_path, parent=None, **kwargs):
        super().__init__(parent, **kwargs)
        #------load configuration from config file-------------------
        config_file_name = 'config.ini'
        config = ConfigParser()
        config_file = join(current_file_path, config_file_name)
        config.read(config_file)
        self.uri = config.get('server', 'uri')
        self.endpoint = config.get('server', 'endpoint')
        self.server_refresh_rate = float(
            config.get('server', 'server_refresh_rate'))
        self.database_file = config.get('server', 'database_file')
        plc_address = config.get('server', 'plc_address')
        ip_address = plc_address.split(':')
        print(ip_address)
        self.plc_ip_address = ip_address[0]
        self.port_number = ip_address[1]
        self.server = opc_server.main_server
        self.terminate = False
        self.queue = Queue()
        self.namespace_index = 0
        
        #------open node sctructure excel file-----------------------
        self.server_ns = opc_server.server_ns#ns()
        self.node_structure = self.server_ns.node_structure



        # -----------------clock------------------------
        self.system_clock = 0
        self.sub_time = 10
        self.hmi_sub = 10

    def run(self):
        asyncio.run(self.opc_server())

    async def subscribe_node(self, node_list:list, handler:object, subscription_time:int, namespace_index:int, queue_size:int):
        """method to subscribe to node data change

        Args:
            node_list (list): list of node(int). Can also input a single node in a list
            handler (class): datachange handler class
            subscription_time (int): delay time of subscription in ms
            namespace_index (int): index number of server name space
            queue_size (int): 0 or 1 for default queue size (shall be 1 - no queuing), n for FIFO queue
        """
        sub = await self.server.create_subscription(subscription_time, handler)
        for node in node_list:
            var = self.server_get_node(node,self.namespace_index)#ua.NodeId(node, namespace_index))
            await sub.subscribe_data_change(var, queuesize=queue_size)

    async def write_queue(self, reader, writer):
        if not self.queue.empty():
            write_data = self.queue.get()
            self.queue.join()
            node_id, data_value = write_data[0], write_data[1]
            data_format = self.node_structure[node_id]['data_type']
            start_device = self.node_structure[node_id]['plc_address']
            await plc_tcp_socket_write_request(start_device, data_value, data_format, reader, writer)

    async def scan_loop_plc(self, lead_device, data_format: int, device_size, io_dict_keys, reader, writer):
        """send the socket request loop to plc
        Args:
            io_dict (dict): dictionary
            data_format (int): 16 or 32 bit
        """
        current_relay_list = await plc_tcp_socket_read_request(lead_device, device_size, data_format, reader, writer)
        io_zip = zip(io_dict_keys, current_relay_list)
        io_zip_list = list(io_zip)
        for node in io_zip_list:
            await self.write_to_opc(node[0], self.namespace_index, node[1])#, data_format)

    async def node_creation(self, database_file, node_category_list,namespace_index):
        conn = sqlite3.connect(database_file)
        for category in node_category_list:
            server_obj = await self.server.nodes.objects.add_object(namespace_index, category)
            for key, value in self.node_structure.items():
                if value['category'] == category:
                    node_id, variable_name, data_type, rw_status, historizing = key, value[
                        'node_name'], value['data_type'], value['rw'], value['history']
                    if historizing == True and checkTableExists(conn, f"{namespace_index}_{node_id}"):
                        initial_value = get_historized_value(conn, namespace_index,node_id, data_type)
                    else:
                        initial_value = value['value']
                    #server_var = await server_obj.add_variable(ua.NodeId(node_id, self.namespace_index), str(variable_name), ua_variant_data_type(data_type, initial_value))
                    node_object = self.server_get_node(node_id,self.namespace_index)
                    server_var = await server_obj.add_variable(node_object.nodeid, str(variable_name), ua_variant_data_type(data_type, initial_value))
                    if rw_status:
                        await server_var.set_writable()
                    if historizing: 
                        await self.server.historize_node_data_change(server_var, period=None, count=10)                    
                  
        conn.close()

    def create_scan_loop_dictionary(self, output_node_category):
        output_dict = {}
        for items in output_node_category:
            dict = {key: value for key, value in self.node_structure.items()
                    if value['category'] == items}
            dict_size = len(dict)
            values_view = dict.values()
            value_iterator = iter(values_view)
            first_value = next(value_iterator)
            data_format = first_value['data_type']
            dict_keys_list = list(dict.keys())
            lead_data = next(iter(dict))
            lead_device = self.node_structure[lead_data]['plc_address']
            output_dict.update(
                {items: [lead_device, data_format, dict_size, dict_keys_list]})
        return output_dict

    async def server_clock(self):
        current_time = datetime.now()
        #await self.write_to_opc(self.server_ns.milli_seconds_node, self.namespace_index, current_time.)
        await self.write_to_opc(self.server_ns.seconds_node, self.namespace_index, current_time.second)
        await self.write_to_opc(self.server_ns.minutes_node,  self.namespace_index, current_time.minute)
        await self.write_to_opc(self.server_ns.hours_node, self.namespace_index, current_time.hour)
        await self.write_to_opc(self.server_ns.days_node, self.namespace_index, current_time.day)
        await self.write_to_opc(self.server_ns.months_node, self.namespace_index, current_time.month)
        await self.write_to_opc(self.server_ns.years_node, self.namespace_index, current_time.year)
    
    async def opc_server(self):
        # Configure server to use sqlite as history database (default is a simple memory dict)
        self.server.iserver.history_manager.set_storage(
            HistorySQLite(self.database_file))
        await self.server.init()
        # populate the server with the defined nodes imported from io_layout_map
        self.server.set_endpoint(f"opc.tcp://{self.endpoint}")
        self.namespace_index = await self.server.register_namespace(self.uri)
        # building node from excel file
        node_cat = [item['category'] for item in self.node_structure.values()]
        node_category = list(set(node_cat))
        await self.node_creation(self.database_file, node_category, self.namespace_index)
        

        # create dictionary of plc address to read
        output_category = [item['category'] for item in self.node_structure.values(
        ) if item['io_type'] == 'output']
        output_node_category = list(set(output_category))
        output_dict = self.create_scan_loop_dictionary(output_node_category)

        
        hmi_input_list = [key for key, value in self.node_structure.items(
        ) if value['io_type'] == 'input']
        hmi_handler = SubHmiHandler(self.queue)
        await self.subscribe_node(hmi_input_list,hmi_handler,2,self.namespace_index,1)
        
        #----WP Validation
        wp_handler = SubWPValidationHandler(self.namespace_index)
        await self.subscribe_node(self.server_ns.wp_validation_trigger, wp_handler, 2, self.namespace_index, 1)

        #----Alarm
        alarm_handler = SubAlarmHandler(self.alarm_signal)
        await self.subscribe_node(self.server_ns.alarm_nodes, alarm_handler,2,self.namespace_index,1)

        #----Monitored node
        monitored_node_handler = SubMonitoredNodes(self.namespace_index, self.label_update_signal)
        await self.subscribe_node(self.server_ns.monitored_node,monitored_node_handler,2,self.namespace_index,1) 
        
        #----IO Relay node
        input_sub_label_handler = SubInputLabelHandler(self.input_relay_signal)
        output_sub_label_handler = SubOutputLabelHandler(self.output_relay_signal)
        await self.subscribe_node(self.server_ns.input_relay_nodes, input_sub_label_handler,2,self.namespace_index,1)
        await self.subscribe_node(self.server_ns.output_relay_nodes, output_sub_label_handler,2,self.namespace_index,1)
        
        #----Encoder Handler
        encoder_sub_label_handler = SubEncoderHandler(self.encoder_pos_signal)
        await self.subscribe_node(self.server_ns.encoder_pos_nodes, encoder_sub_label_handler,2,self.namespace_index,1)

        #----Device Status
        device_status_handler = SubDeviceStatusHandler(self.device_status_signal)
        await self.subscribe_node(self.server_ns.device_status_nodes, device_status_handler,2,self.namespace_index,1)

        #----Module Status
        module_status_handler = SubModuleStatusHandler(self.module_status_signal)
        await self.subscribe_node(self.server_ns.module_status_nodes, module_status_handler,2,self.namespace_index,1)

        #----Machine Status
        machine_status_handler = SubMachineStatusHandler(self.namespace_index,self.machine_status_signal)
        await self.subscribe_node(self.server_ns.machine_status_node, machine_status_handler,2,self.namespace_index,1)

        #----ID Track
        id_track_handler = SubIDTrackHandler(self.id_track_signal)
        line_1_id_track_list = [node_id for node_id in self.server_ns.get_node_list_by_category('plc_id_track') if '_line_1' in self.server_ns.read_label_node_structure(node_id)[0]]
        await self.subscribe_node(line_1_id_track_list, id_track_handler,10,self.namespace_index,1)
        
        #-----server clock handlers
        second_interval_handler = SubSecondsHandler(self.seconds_signal,self.namespace_index, self.oee_time_signal)
        await self.subscribe_node([10045],second_interval_handler,10,self.namespace_index,1)

        minute_interval_handler = SubMinutesHandler(self.database_file,self.namespace_index, self.minutes_signal,self.label_update_signal,self.uph_update_signal, self.reset_lot_oee_signal)
        await self.subscribe_node([10044],minute_interval_handler,10,self.namespace_index,1)

        hour_interval_handler = SubHoursHandler(self.hours_signal)
        await self.subscribe_node([10043],hour_interval_handler,10,self.namespace_index,1)

        day_interval_handler = SubDaysHandler(self.days_signal)
        await self.subscribe_node([10042],day_interval_handler,10,self.namespace_index,1)

        month_interval_handler = SubMonthsHandler(self.months_signal)
        await self.subscribe_node([10041],month_interval_handler,10,self.namespace_index,1)

        year_interval_handler = SubYearsHandler(self.years_signal)
        await self.subscribe_node([10040],year_interval_handler,10,self.namespace_index,1)
        #test_int = 0
        #print(output_dict)
        self.initialize_ui_label.emit()
        async with self.server:
            reader, writer = await asyncio.open_connection(self.plc_ip_address, self.port_number)
            while not self.terminate:
                for (lead_device, data_type, device_size, dict_keys_list) in output_dict.values():
                    await self.scan_loop_plc(lead_device, data_type, device_size, dict_keys_list, reader, writer)
                    await self.write_queue(reader, writer)

                await self.server_clock()
                await asyncio.sleep(0.01)
                #await self.write_to_opc(self.server_ns.lot_out_qty_node,self.namespace_index,test_int)
                #test_int += 1

                self.terminate = not await self.read_from_opc(12014, self.namespace_index)
            await plc_tcp_socket_write_request("MR114", 0, "Boolean", reader, writer)
            writer.close()
        
        


