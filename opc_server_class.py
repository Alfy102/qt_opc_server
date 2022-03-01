
from asyncua import Server, ua
from data_handler import month_str, ua_variant_data_type,byte_swap_method, str_to_list, data_type_conversion
from datetime import datetime
from os.path import join, realpath, dirname
from sys import argv
import xlrd

class NodeStructure():
    def __init__(self):
        file_path = dirname(realpath(argv[0]))
        excel_loc = join(file_path, 'node_structure.xls')
        node_structure = self.load_node_structure(excel_loc,0)
        monitored_node = self.load_node_structure(excel_loc,1)
        self.alarm_table = self.load_alarm_table(excel_loc,2)
        for node_id in monitored_node:
            monitored_nodes_list = str_to_list(monitored_node[node_id]['list'])   
            monitored_node[node_id]['list'] = monitored_nodes_list
        
        for node_id in node_structure:
            node_structure_list = str_to_list(node_structure[node_id]['label_point'])   
            node_structure[node_id]['label_point'] = node_structure_list

        self.node_structure = node_structure
        self.monitored_node = monitored_node
        self.dry_cycle_node = self.get_node_list_by_name('HMI Dry Cycle')[0]#12003
        self.hmi_manual_mode = self.get_node_list_by_name('HMI Manual')[0]#12005
        self.bypass_api = self.get_node_list_by_name('bypass_api_request')[0]#10700
        self.validation_pass_node = self.get_node_list_by_name('WP Validation Pass')[0]#12012
        self.validation_fail_node = self.get_node_list_by_name('WP Validation Fail')[0]#12013
        self.validation_done_node = self.get_node_list_by_name('WP_Validation_Done')[0]#12015
        self.wp_validation_trigger = self.get_node_list_by_name('wp_validation_trigger')

        self.lot_in_qty_node = self.get_node_list_by_name('lot_total_quantity_in')[0]
        self.lot_out_qty_node = self.get_node_list_by_name('lot_total_quantity_out')[0]
        self.lot_total_yield_node = self.get_node_list_by_name('lot_total_yield')[0]

        self.shift_in_qty_node = self.get_node_list_by_name('oee_total_quantity_in')[0]
        self.shift_out_qty_node = self.get_node_list_by_name('oee_total_quantity_out')[0]
        self.shift_total_yield_node = self.get_node_list_by_name('oee_total_yield')[0]
        
        self.lot_input_nodes = self.get_node_list_by_category('lot_input')

        self.recipe_name = self.get_node_list_by_name('recipe_name')[0]

        self.lot_total_pass_node = self.get_node_list_by_name('lot_total_pass')[0]
        self.lot_total_fail_node = self.get_node_list_by_name('lot_total_fail')[0]
        self.oee_total_pass_node = self.get_node_list_by_name('oee_total_pass')[0]
        self.oee_total_fail_node = self.get_node_list_by_name('oee_total_fail')[0]

        self.light_tower_list = self.get_node_list_by_category('light_tower_settings')
        self.uph_minute_node = self.get_node_list_by_name('production_uph')[0]
        

        self.machine_running_node = self.get_node_list_by_name('RUNNING')[0]
        self.error_count_node = self.get_node_list_by_name('error_count')[0]

        self.seconds_node = self.get_node_list_by_name('server_second')[0]
        self.hours_node = self.get_node_list_by_name('server_hou')[0]
        self.minutes_node = self.get_node_list_by_name('server_minute')[0]
        self.days_node = self.get_node_list_by_name('server_day')[0]
        self.months_node = self.get_node_list_by_name('server_month')[0]
        self.years_node = self.get_node_list_by_name('server_year')[0]
        self.uph_plot_node = self.get_node_list_by_category('uph_variables')

        self.lot_uptime_node = self.get_node_list_by_name('lot_uptime')[0]
        self.lot_operation_time_node = self.get_node_list_by_name('lot_operation_time')[0]
        self.lot_down_time_node = self.get_node_list_by_name('lot_down_time')[0]
        self.lot_idling_time_node = self.get_node_list_by_name('lot_idling_time')[0]
        self.lot_maintenance_time_node = self.get_node_list_by_name('lot_maintenance')[0]
        self.lot_no_material_time_node = self.get_node_list_by_name('lot_no_material')[0]
        self.oee_time_node = self.get_node_list_by_name('oee_time')[0]
        self.oee_operation_time_node = self.get_node_list_by_name('oee_operation_time')[0]
        self.oee_down_time_node = self.get_node_list_by_name('oee_down_time')[0]
        self.oee_idling_time_node = self.get_node_list_by_name('oee_idling_time')[0]

        self.light_tower_input_nodes = self.get_node_list_by_name('Input Light Tower')
        self.id_track_clear_nodes = self.get_node_list_by_category('id_track_clear')

        self.machine_status_node = self.get_node_list_by_category('machine_status')
        self.server_clock = self.get_node_list_by_category('server_clock')
        self.server_variable_list = self.get_node_list_by_category('server_variables')
        self.time_variable_list = self.get_node_list_by_category('time_variables')
        self.motor_1_properties = self.get_node_list_by_category('motor_1_properties')
        self.motor_2_properties = self.get_node_list_by_category('motor_2_properties')
        self.motor_3_properties = self.get_node_list_by_category('motor_3_properties')
        self.motor_4_properties = self.get_node_list_by_category('motor_4_properties')
        self.motor_6_properties = self.get_node_list_by_category('motor_6_properties')
        self.laser_1_properties = self.get_node_list_by_category('laser_1_recipe')
        self.laser_2_properties = self.get_node_list_by_category('laser_2_recipe')
        
        self.user_access_settings = self.get_node_list_by_category('user_access')
        self.login_credentials_nodes = self.get_node_list_by_category('login_credentials')
        self.api_config = self.get_node_list_by_category('api_url')
        self.encoder_list = self.get_node_list_by_category('encoder_position')

        self.input_relay_nodes = self.get_node_list_by_category('input_relay')
        self.output_relay_nodes = self.get_node_list_by_category('output_relay')
        self.alarm_nodes = self.get_node_list_by_category('alarm')
        self.encoder_pos_nodes = self.get_node_list_by_category('encoder_position')
        self.device_status_nodes = self.get_node_list_by_category('device_status')
        self.module_status_nodes = self.get_node_list_by_category('module_status')

        self.motor_go_input_nodes = self.get_node_list_by_category('motor_go_input')
        self.motor_state_input_nodes = self.get_node_list_by_category('motor_state_input')

        self.shift_start_time_node = self.get_node_list_by_category('shift_start_time')

        self.system_exit_node = self.get_node_list_by_name('System Exit')[0]



    def get_category_list(self):
        node_cat = [item['category'] for item in self.node_structure.values()]
        node_category = list(set(node_cat))
        return node_category

    def update_node_structure(self, node_id:int, data:any):
        data_type = self.read_data_type_node_structure(node_id)
        new_data = data_type_conversion(data_type, data)
        self.node_structure[node_id]['value']=new_data

    def read_value_node_structure(self, node_id):
        data_type = self.read_data_type_node_structure(node_id)
        value = self.node_structure[node_id]['value']
        new_data = data_type_conversion(data_type, value)
        return new_data

    def get_node_list_by_name(self, ref_str:str):
        """return list of nodes for the node structure by name or label_point

        Args:
            ref_str (str): either node_name or label_name

        Returns:
            list: list of nodes
        """
        node_list = [node for node, value in self.node_structure.items(
            ) if node in self.node_structure if (ref_str in value['node_name']) or (ref_str in value['label_point'])]
        return node_list

    def get_node_list_by_category(self, node_category):
        """get node list by category

        Args:
            node_category (str): name of said category

        Returns:
            list: list of nodes
        """
        return [node for node, value in self.node_structure.items() if value['category'] == node_category]

    def read_name_node_structure(self,node_id):
        name = self.node_structure[node_id]['node_name']
        return name

    def read_label_node_structure(self, node_id):
        label = self.node_structure[node_id]['label_point']
        return label

    def read_data_type_node_structure(self, node_id):
        data_type = self.node_structure[node_id]['data_type']
        return data_type

    def load_alarm_table(self,file_loc,sheet_number:int):
        ws = xlrd.open_workbook(file_loc)
        sheet = ws.sheet_by_index(sheet_number)
        rows = sheet.nrows
        columns = sheet.ncols
        dict_keys = [int(sheet.cell_value(i, 0)) for i in range(1, rows)]
        node_structure = {}
        for i, node in enumerate(dict_keys):
            node_structure.update({node: (sheet.cell_value(i+1, 1).strip())})
        return node_structure

    def id_track_node(self, track_number):
        node_number_tuple = self.get_node_list_by_name(f"PLC_slot_{track_number}_")
        return tuple(node_number_tuple)

    def load_node_structure(self, file_loc,sheet_number:int):
        """load node structure from excel tables into dictionary

        Args:
            file_loc (str): file path of the node structure excel file
            sheet_number (int): index number of sheet that contains the node structure table

        Returns:
            dict: node structure dictionary
        """
        # For row 0 and column 0, index 0 for first sheet
        ws = xlrd.open_workbook(file_loc)
        sheet = ws.sheet_by_index(sheet_number)
        rows = sheet.nrows
        columns = sheet.ncols
        sub_dict_keys = [sheet.cell_value(0, i) for i in range(1, columns)]
        dict_keys = [int(sheet.cell_value(i, 0)) for i in range(1, rows)]
        node_structure = {}
        for i, node in enumerate(dict_keys):
            sub_dict = {}
            for j, sub_item in enumerate(sub_dict_keys):
                sub_dict.update({sub_item: sheet.cell_value(i+1, j+1)})
            node_structure.update({node: sub_dict})
        return node_structure

class OpcServerClass():
    main_server = Server()
    server_ns = NodeStructure()
    async def read_from_opc(self, node_id: int,namespace_index):
        var = self.main_server.get_node(ua.NodeId(node_id, namespace_index))
        data = await var.read_value()
        return data

    async def write_to_opc(self, node_id: int, namespace_index, data_value: any, data_type=None):
        node = self.main_server.get_node(ua.NodeId(node_id, namespace_index))
        if data_type == None:
            data_type = self.server_ns.read_data_type_node_structure(node_id)
        source_time = datetime.now()
        data_value = ua.DataValue(ua_variant_data_type(
            data_type, data_value), SourceTimestamp=source_time, ServerTimestamp=source_time)
        await self.main_server.write_attribute_value(node.nodeid, data_value)


    async def wp_serial_pn_gen(self, namespace_index:int, track_number:int):    
        """_summary_

        Args:
            namespace_index (int): _description_
            track_number (int): _description_

        Returns:
            tuple: (unit_present, runner_count,wp_part_number,wp_dimension,bcr_1_status,bcr_2_status,wp_validation_status,wp_serial)
        """
        unit_present_node , runner_count_node, wp_part_number_1_node, wp_part_number_2_node, wp_dimension_node, bcr_1_node, bcr_2_node, wp_validation_node, Spare_1_node, Spare_2_node = self.server_ns.id_track_node(track_number)
        unit_present = await self.read_from_opc(unit_present_node, namespace_index)
        runner_count_dec = await self.read_from_opc(runner_count_node, namespace_index)
        runner_count = byte_swap_method(runner_count_dec)
        wp_part_1 = await self.read_from_opc(wp_part_number_1_node, namespace_index)
        wp_part_2 = await self.read_from_opc(wp_part_number_2_node, namespace_index)
        wp1_str = byte_swap_method(wp_part_1)
        wp2_str = byte_swap_method(wp_part_2)
        wp_part_number = f"{wp1_str}{wp2_str}"
        wp_dimension = await self.read_from_opc(wp_dimension_node, namespace_index)
        bcr_1_status = await self.read_from_opc(bcr_1_node, namespace_index)
        bcr_2_status = await self.read_from_opc(bcr_2_node, namespace_index)
        wp_validation_status = await self.read_from_opc(wp_validation_node, namespace_index)
        current_year = await self.read_from_opc(self.server_ns.years_node, namespace_index) #get current year
        current_month = await self.read_from_opc(self.server_ns.months_node, namespace_index) #get current month
        current_month_str = month_str(current_month)
        wp_serial = f"WP{str(current_year)[-2:]}{current_month_str}{wp_dimension}Z{runner_count}" 
        return_package = (unit_present, runner_count,wp_part_number,wp_dimension,bcr_1_status,bcr_2_status,wp_validation_status,wp_serial)
        return return_package

    def server_get_node(self, node_id: int, namespace_index):
        """This function will get the node object of a nodeid

        Args:
            node_id ([tint): [description]

        Returns:
            object: node object
        """
        node = self.main_server.get_node(ua.NodeId(node_id, namespace_index))
        return node

