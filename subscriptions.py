from platform import machine
import sqlite3
import asyncio
from datetime import datetime, timedelta, date
from unicodedata import name
from wsgiref.simple_server import server_version
from data_handler import uph_array_calculation, uph_calculation, time_calculation, create_table, conn_commit
import xml.etree.ElementTree as ET
import requests
from opc_server_class import OpcServerClass as opc_server
from time import time_ns


class SubHmiHandler(object):
    def __init__(self, input_q):  
        """initialise SubHmiHandler, this class handles all input data to PLC.

        Args:
            input_q (queue function): pass the input queue from the datachange to write to hmi.
        """
        self.input_q = input_q

    async def datachange_notification(self, node, val, data):
        """This will be called whenever a datachange happens on the subscribed node

        Args:
            node (node object): [description]
            val (int or string): [description]
            data (monitored_data object): [description]
        """
        node_identifier = node.nodeid.Identifier
        self.input_q.put((node_identifier, val), block=False, timeout=None)
        self.input_q.task_done()


class SubMonitoredNodes(opc_server):
    def __init__(self, namespace_index, update_ui_label):
        super().__init__()
        self.label_update_signal = update_ui_label
        self.server_ns = opc_server.server_ns#ns()  
        self.namespace_index = namespace_index     
        self.monitored_node_dict = self.server_ns.monitored_node

    async def datachange_notification(self, node, val, data):
        node_id = node.nodeid.Identifier
        monitored_nodes = self.monitored_node_dict[node_id]['list']
        if val == 1:
            await self.node_count(monitored_nodes, val)
        #print(self.server_ns.lot_in_qty_node)
        await self.yield_calculation(self.server_ns.lot_in_qty_node, self.server_ns.lot_out_qty_node, self.server_ns.lot_total_yield_node)
        await self.yield_calculation(self.server_ns.shift_in_qty_node, self.server_ns.shift_out_qty_node, self.server_ns.shift_total_yield_node)

    async def yield_calculation(self, in_qty_node, out_qty_node, yield_node):
        in_value = await self.sub_read_from_opc(in_qty_node)#await self.read_from_opc(in_qty_node,self.namespace_index)
        out_value = await self.sub_read_from_opc(out_qty_node)#,self.namespace_index)
        lot_yield = self.lot_yield_calculation(in_value, out_value)
        lot_yield = round(lot_yield, 2)
        lot_yield_str = str(lot_yield)
        self.label_update_method(yield_node, lot_yield_str)

    async def node_count(self, monitored_node_list: list, data_value: int):
        #if await self.read_opc(self.machine_run_node):
        for node_id in monitored_node_list:
            count = await self.sub_read_from_opc(node_id)#, self.namespace_index)
            count += data_value
            await self.sub_write_to_opc(node_id, count)
            count_str = str(count)
            self.label_update_method(node_id, count_str)

    def lot_yield_calculation(self, in_value: int, out_value: int):
        try:
            lot_yield = (out_value / in_value) * 100
        except:
            lot_yield = 0
        lot_yield = round(lot_yield, 2)
        return lot_yield
    
    def label_update_method(self, node_id, label_str):
        node_label = self.server_ns.read_label_node_structure(node_id)
        self.label_update_signal.emit(node_label, label_str)
        
    async def sub_write_to_opc(self, node_id, write_value):
        #data_type = self.server_ns.read_data_type_node_structure(node_id)
        await self.write_to_opc(node_id, self.namespace_index, write_value)#,data_type)

    async def sub_read_from_opc(self, node_id):
        read_value = await self.read_from_opc(node_id,self.namespace_index)
        return read_value

class SubInputLabelHandler(object):
    def __init__(self, input_relay_signal):
        self.input_relay_signal = input_relay_signal

    async def datachange_notification(self, node, val, data):
        node_id = node.nodeid.Identifier
        self.input_relay_signal.emit(node_id, val)

class SubOutputLabelHandler(object):
    def __init__(self, output_relay_signal):
        self.output_relay_signal = output_relay_signal

    async def datachange_notification(self, node, val, data):
        node_id = node.nodeid.Identifier
        self.output_relay_signal.emit(node_id, val)

class SubDeviceStatusHandler(object):
    def __init__(self, pyqt_signal):
        self.pyqt_signal = pyqt_signal

    async def datachange_notification(self, node, val, data):
        node_id = node.nodeid.Identifier
        self.pyqt_signal.emit(node_id, val)

class SubEncoderHandler(object):
    def __init__(self, encoder_label_update):
        self.encoder_label_update = encoder_label_update
    async def datachange_notification(self, node, val, data):
        node_id = node.nodeid.Identifier
        self.encoder_label_update.emit(node_id)

class SubWPValidationHandler(opc_server):
    def __init__(self, namespace_index):  
        super().__init__()
        self.namespace_index = namespace_index
 

    async def datachange_notification(self, node, val, data):
        node_identifier = node.nodeid.Identifier
        await self.write_to_opc(self.server_ns.validation_pass_node, self.namespace_index, False)
        await self.write_to_opc(self.server_ns.validation_fail_node, self.namespace_index, False)
        await self.write_to_opc(self.server_ns.validation_done_node, self.namespace_index, False)
        if val == True:
            id_track_4_data = await self.wp_serial_pn_gen(self.namespace_index, 4)
            wp_serial = id_track_4_data[7]
            wp_partnum = id_track_4_data[2]
            unit_present = id_track_4_data[0]
            wp_validation_result = await self.wp_validate_api_request(unit_present, wp_serial, wp_partnum)
            if wp_validation_result == None:
                pass
            elif 'OK' in wp_validation_result and unit_present:
                await self.write_to_opc(self.server_ns.validation_pass_node, self.namespace_index, True)
            elif unit_present:
                await self.write_to_opc(self.server_ns.validation_fail_node, self.namespace_index, True)
            await self.write_to_opc(self.server_ns.validation_done_node, self.namespace_index, True)

        
        
        

    async def wp_validate_api_request(self,unit_present, wp_serial, wp_partnum):
        payload = """<soapenv:Envelope xmlns:soapenv="example_link" xmlns:tem="example_link">
                <soapenv:Header/>
                <soapenv:Body>
                    <tem:InsertWP>
                        <!--Optional:-->
                        <tem:WP>{wp_serial}</tem:WP>
                        <!--Optional:-->
                        <tem:PN>{wp_partnum}</tem:PN>
                    </tem:InsertWP>
               </soapenv:Body>
            </soapenv:Envelope>"""
        payload_formatted = payload.format(wp_serial=wp_serial, wp_partnum=wp_partnum)
        payload_encoded = payload_formatted.encode('utf-8')
        headers = {"Content-Type": "text/xml; charset=utf-8"}
        wp_validation_result=None
        bypass_api = await self.read_from_opc(self.server_ns.bypass_api, self.namespace_index)
        hmi_manual = await self.read_from_opc(self.server_ns.hmi_manual_mode, self.namespace_index)
        dry_cycle = await self.read_from_opc(self.server_ns.dry_cycle_node, self.namespace_index)
        if any([bypass_api,hmi_manual,dry_cycle]):
            wp_validation_result = 'OK'
        elif unit_present:
            api_url = await self.read_from_opc(10830, 2) 
            try:
                response = requests.request("POST", api_url, headers=headers, data=payload_encoded)
                start_idx = response.index('<InsertWPResult>')
                end_idx = response.index('</InsertWPResponse>')
                xml_cut = response[start_idx:end_idx]
                responseXml = ET.fromstring(xml_cut)
                wp_validation_result = responseXml.text
            except:
                wp_validation_result = 'OK'
        return wp_validation_result

class SubModuleStatusHandler(object):
    def __init__(self, pyqt_signal):
        self.pyqt_signal = pyqt_signal

    async def datachange_notification(self, node, val, data):
        node_id = node.nodeid.Identifier
        self.pyqt_signal.emit(node_id, val)

class SubIDTrackHandler(object):
    def __init__(self,id_track_signal):
        self.id_track_signal = id_track_signal

    async def datachange_notification(self, node, val, data):
        node_id = node.nodeid.Identifier
        self.id_track_signal.emit(node_id, val)

class SubAlarmHandler(object):
    def __init__(self, pyqt_signal):
        self.pyqt_signal = pyqt_signal

    async def datachange_notification(self, node, val, data):
        node_id = node.nodeid.Identifier
        self.pyqt_signal.emit(node_id, val)

class SubUPHHandler(opc_server):
    def __init__(self, database_file, namespace_index, label_update_signal,uph_update_signal):
        super().__init__(database_file, namespace_index)
        self.namespace_index = namespace_index
        self.uph_30min_interval = []
        self.uph_minute_interval = [0, 0]
        self.label_update_signal = label_update_signal
        self.uph_update_signal = uph_update_signal
        #self.conn = sqlite3.connect(database_file)

    async def uph_minute_calculation(self):
        lot_qty_out = await self.read_from_opc(self.server_ns.lot_out_qty_node, self.namespace_index)
        self.uph_minute_interval, uph_minute = uph_calculation(self.uph_minute_interval,lot_qty_out)      
        label_str = self.server_ns.read_label_node_structure(self.server_ns.uph_minute_node)
        uph_minute_str = str(uph_minute)
        self.label_update_signal.emit(label_str, uph_minute_str)
        await self.write_to_opc(self.server_ns.uph_minute_node, self.namespace_index, uph_minute)

        #if await self.read_from_opc(self.server_ns.machine_running_node, self.namespace_index):
        if uph_minute != 0:
            self.uph_30min_interval.append(uph_minute)

    async def uph_30_minute_calculation(self, current_minute):
        average_uph = uph_array_calculation(self.uph_30min_interval)
        hour = await self.read_from_opc(self.server_ns.hours_node, self.namespace_index)
        node_name = f"uph_{hour:02d}_{current_minute:02d}"
        node_list = self.server_ns.get_node_list_by_name(node_name)
        node_id = node_list[0]
        await self.write_to_opc(node_id, self.namespace_index, average_uph)
        self.uph_30min_interval.clear()
        self.uph_update_signal.emit()

class SubMachineStatusHandler(opc_server):
    def __init__(self, namespace_index, machine_status_signal):
        self.machine_status_signal = machine_status_signal
        self.namespace_index = namespace_index
    async def datachange_notification(self, node, val, data):
        node_id = node.nodeid.Identifier
        self.machine_status_signal.emit()#node_id, val)
        await self.light_tower_output()
    

    async def light_tower_output(self):
        machine_state = [int(await self.read_from_opc(node_id, self.namespace_index)) for node_id in self.server_ns.machine_status_node]
        try:
            machine_idx = machine_state.index(1)
        except:
            machine_idx = None
        
        if machine_idx != None:
            light_tower_node = self.server_ns.light_tower_list[machine_idx]
            light_tower_configuration = await self.read_from_opc(light_tower_node, self.namespace_index)
            light_tower_configuration_list = light_tower_configuration.split(',')
            for i,lt_nodes in enumerate(self.server_ns.light_tower_input_nodes):
                await self.write_to_opc(lt_nodes, self.namespace_index, light_tower_configuration_list[i]) 


        else:
            for node_id in self.server_ns.light_tower_input_nodes:
                await self.write_to_opc(node_id, self.namespace_index, False)




class SubOeeTimehandler(opc_server):
    def __init__(self,namespace_index, oee_time_signal):
        super().__init__()
        self.namespace_index = namespace_index
        self.oee_time_signal = oee_time_signal
        self.run_time_table = {}

    async def oee_time_calculation(self,machine_state):   
        running, stopping, alarm, no_material,maint_mode = machine_state

        if running:
            await self.machine_running([self.server_ns.lot_uptime_node, self.server_ns.lot_operation_time_node, self.server_ns.oee_operation_time_node])
        elif stopping or alarm:
            await self.machine_running([self.server_ns.lot_down_time_node, self.server_ns.oee_down_time_node])
        elif no_material:
            await self.machine_running([self.server_ns.lot_no_material_time_node])
        elif maint_mode:
            await self.machine_running([self.server_ns.lot_maintenance_time_node])
        else:
            await self.machine_running([self.server_ns.lot_idling_time_node, self.server_ns.oee_idling_time_node])


    async def machine_running(self, time_list_node):
        for node_id in time_list_node: 
            previous_time = await self.read_from_opc(node_id, self.namespace_index)
            duration = time_calculation(previous_time)  
            await self.write_to_opc(node_id,self.namespace_index,duration)
            self.oee_time_signal.emit(node_id, duration)



class SubOeeHistorizingHandler(opc_server):
    def __init__(self,database_file, namespace_index):
        super().__init__()
        self.conn = sqlite3.connect(database_file)
        self.namespace_index = namespace_index
        create_table(self.conn)


    async def get_time(self):
        server_time = [await self.read_from_opc(node_id, self.namespace_index) for node_id in self.server_ns.server_clock]
        time = f"{server_time[0]}-{server_time[1]:02d}-{server_time[2]:02d} {server_time[3]:02d}:{server_time[4]:02d}"
        return time



    async def insert_into_table(self,recipe):
        dt_string = await self.get_time()
        error_count = await self.read_from_opc(self.server_ns.error_count_node, self.namespace_index)
        total_pass = await self.read_from_opc(self.server_ns.lot_total_pass_node, self.namespace_index)
        total_fail = await self.read_from_opc(self.server_ns.lot_total_fail_node, self.namespace_index)
        quantity_in = await self.read_from_opc(self.server_ns.lot_in_qty_node, self.namespace_index)
        quantity_out = await self.read_from_opc(self.server_ns.lot_out_qty_node, self.namespace_index)
        total_yield = await self.read_from_opc(self.server_ns.lot_total_yield_node, self.namespace_index)
        insert_data = f"""
            INSERT INTO oee_data (datetime, recipe, error_count, total_pass, total_fail, quantity_in, quantity_out, total_yield)
            VALUES ('{dt_string}', '{recipe}', '{error_count}', '{total_pass}', '{total_fail}', '{quantity_in}', '{quantity_out}', '{total_yield}');
            """

        conn_commit(self.conn, insert_data)

    def remove_oldest_row(self,oldest_data_duration:int):
        dt = datetime.now()
        last_dt = dt - timedelta(days=oldest_data_duration)
        last_dt_string = last_dt.strftime("%Y-%m-%d %H:%M")

        table_delete = f"""
            DELETE FROM oee_data WHERE datetime <= '{last_dt_string}'

                """
        conn_commit(self.conn, table_delete)

