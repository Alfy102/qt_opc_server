from inspect import getattr_static
from platform import node
import sqlite3
import asyncio
from sys import argv, exit, stdout, executable
from os import execl
from os.path import dirname, realpath, join
from PyQt6 import QtCore, QtWidgets
from PyQt6.QtCore import QThread, QTimer,pyqtSlot
from PyQt6.QtWidgets import QMainWindow, QHeaderView, QCheckBox, QLineEdit, QLabel
#from data_handler import NodeStructure as ns
from data_handler import byte_swap_method,str_to_list
import opc_platform_server as main_server
from main_gui import Ui_MainWindow as gui
import win32con
import win32api
from win32api import GetLogicalDriveStrings
from win32file import GetDriveType
from datetime import datetime

from dialog import MessageBox,ExportOeeDialog, ExportLogsDialog, Dialog
from csv import writer

from configparser import ConfigParser
from PyQt6.QtWidgets import QTableWidgetItem
from PyQt6.QtGui import QIntValidator

from opc_server_class import OpcServerClass as opc_server
class Ui_MainWindow(QMainWindow, gui, opc_server):
    def __init__(self):
        super(Ui_MainWindow, self).__init__()
        config = ConfigParser()
        config_file_name = 'config.ini'
        file_path = dirname(realpath(argv[0]))
        config_file = join(file_path, config_file_name)
        config.read(config_file)
        # -------client worker thread and signals initialisation-----
        self.server_thread = QThread()
        self.database_file = config.get('server', 'database_file')
        self.server_worker = main_server.OpcServerThread(file_path)
        self.server_worker.moveToThread(self.server_thread)
        self.server_worker.input_relay_signal.connect(self.input_label_update)
        self.server_worker.output_relay_signal.connect(self.output_label_update)
        self.server_worker.initialize_ui_label.connect(self.initialize_ui)
        self.server_worker.encoder_pos_signal.connect(self.encoder_label_update)
        self.server_worker.seconds_signal.connect(self.internal_seconds)
        self.server_worker.minutes_signal.connect(self.internal_minutes)
        self.server_worker.hours_signal.connect(self.internal_hours)
        self.server_worker.oee_time_signal.connect(self.oee_time_update)
        self.server_worker.days_signal.connect(self.internal_days)
        self.server_worker.months_signal.connect(self.internal_months)
        self.server_worker.years_signal.connect(self.internal_years)
        self.server_worker.label_update_signal.connect(self.label_updater)
        self.server_worker.uph_update_signal.connect(self.uph_update_plot)
        self.server_worker.device_status_signal.connect(self.device_status_update)
        self.server_worker.module_status_signal.connect(self.module_status_update)
        self.server_worker.id_track_signal.connect(self.id_track_update)
        self.server_worker.alarm_signal.connect(self.alarm_status_update)
        self.server_worker.machine_status_signal.connect(self.machine_status_update)
        self.server_worker.reset_lot_oee_signal.connect(self.reset_lot_oee)
        self.server_thread.started.connect(self.server_worker.run)
     
        #-----alarm blinker
        self.blinkingtimer = QTimer()
        self.blinkingtimer.timeout.connect(self.alarm_blinking)
        self.default_font_colour = "color: rgb(255, 255, 255);"
        self.default_bg_colour = "background-color:rgb(51, 53, 74)" 
        self.alarm_state = False
        self.red_font_color = "color: rgb(255, 14, 14);"
        self.white_font_color = "color: rgb(255, 255, 255);"
        self.white_bg = "background-color: rgb(255, 255, 255);"
        self.red_bg = "background-color: rgb(255, 14, 14);"

        #-----id track
        self.selected_track_number = 1
        #-----alarm_dictionary
        self.alarm_table = self.server_ns.alarm_table
        #-----motor
        self.selected_motor = 1
        self.motor_save_node = 12006
        #-----uph
        self.x = [f"{z:02d}:{r*30:02d}" for z in range(0,24) for r in range(0,2)] #create 24H time range
        self.x.append(self.x.pop(self.x.index('00:00')))

        self.uph_dict = ()
        self.y = [0]
        self.plot_bar = None
        self.plot_text = []
        #-----user credentials
        self.level_1 = self.server_ns.get_node_list_by_name('operator_credentials')[0]
        self.level_2 = self.server_ns.get_node_list_by_name('engineer_credentials')[0]
        self.level_3 = self.server_ns.get_node_list_by_name('oem_credentials')[0]
        self.default_access_level = [1,0,1,1,0,1,0,0,0,0,0]
        self.user_level = None
        # ------control IO ON/OFF Color------------------------------
        rgb_value_input_on = "64, 255, 0"
        rgb_value_input_off = "0, 80, 0"
        self.rgb_input_tuple = (rgb_value_input_off, rgb_value_input_on)
        rgb_value_output_on = "255, 20, 20"
        rgb_value_output_off = "80, 0, 0"
        self.rgb_output_tuple = (rgb_value_output_off, rgb_value_output_on)
        self.setupUi(self)

    def initialize_ui(self):
        self.load_config_method(self.server_ns.light_tower_list)
        self.load_shift_time()
        self.load_config_method(self.server_ns.api_config)
        self.load_config_method(self.server_ns.laser_1_properties)
        self.load_config_method(self.server_ns.laser_2_properties)
        self.load_config_method(self.server_ns.user_access_settings)
        self.load_config_method(self.server_ns.server_variable_list)
        self.load_config_method(self.server_ns.time_variable_list)
        self.load_config_method(self.server_ns.motor_1_properties)
        self.load_config_method(self.server_ns.motor_2_properties)
        self.load_config_method(self.server_ns.motor_3_properties)
        self.load_config_method(self.server_ns.motor_4_properties)
        self.load_config_method(self.server_ns.motor_6_properties)
        self.uph_update_plot()
        self.logger_handler("INFO", "Successfully load stored settings")

    def load_shift_time(self):
        [(getattr(self, self.server_ns.read_label_node_structure(node_id)[0]).setTime(datetime.strptime(self.async_run_read_from_opc(node_id), '%H:%M').time())) for node_id in self.server_ns.shift_start_time_node]


    def change_password(self):
        current_idx = self.username_combo_box.currentIndex()
        old_pass = self.old_password_input.text()
        new_pass = self.new_password_input.text()
        re_new_pass = self.retyped_new_password_input.text()

        selected_user_node = getattr(self,f"level_{current_idx+1}")
        stored_password = self.async_run_read_from_opc(selected_user_node)

        if new_pass != re_new_pass:
            self.message_box_show("Password Mismatch. Please Try Again")
        elif new_pass == re_new_pass:
            if old_pass!= stored_password:
                self.message_box_show("Password Mismatch. Please Try Again")
            elif old_pass == stored_password:
                self.async_run_write_to_opc(selected_user_node, new_pass)
                self.message_box_show("New Password Saved")
                user_name = self.server_ns.read_name_node_structure(selected_user_node)
                user_name_split = user_name.split('_')
                print(user_name, user_name_split)
                self.logger_handler("INFO", f"Password change for user:{user_name_split[0]}")

    @pyqtSlot(list)
    def save_config_method(self, node_list):
        for node in node_list:
            label_list = self.server_ns.read_label_node_structure(node)
            ui_object = getattr(self, label_list[0])
            test_type = type(ui_object)
            if test_type is QCheckBox:
                current_value = [str(int(getattr(self, check_box).isChecked())) for check_box in label_list]
                current_value_conv = ",".join(current_value)
            elif test_type is QLineEdit:
                current_value = [(getattr(self, line_edit).text()) for line_edit in label_list]
                current_value_conv = current_value[0]
            self.async_run_write_to_opc(node, current_value_conv)

    @pyqtSlot(list)
    def load_config_method(self, node_list):
        for node in node_list:
            label_list = self.server_ns.read_label_node_structure(node)
            if label_list[0] == 'None':
                continue
            ui_object = getattr(self, label_list[0])
            test_type = type(ui_object)
            stored_value = self.async_run_read_from_opc(node)
            if test_type is QCheckBox:
                split_value = str_to_list(stored_value)
                current_value = [getattr(self, check_box).setChecked(bool(state)) for check_box, state in zip(label_list, split_value)]
            elif test_type is QLineEdit:
                self.label_updater(label_list, stored_value)
            elif test_type is QLabel:
                self.label_updater(label_list, stored_value)

    @pyqtSlot(int)
    def motor_selection(self, motor_number):
        self.selected_motor = motor_number
        self.motor_page_stacked_widget.setCurrentIndex(motor_number-1)
        self.main_motor_control_stacked_widget.setCurrentIndex(motor_number-1)
        for node in self.server_ns.encoder_list:
            node_name = self.server_ns.read_name_node_structure(node)
            if str(self.selected_motor) in node_name:
                self.encoder_label_update(node)

    def save_motor_properties(self):
        self.async_run_write_to_opc(self.motor_save_node, True)
        self.message_box_show("New Settings Saved!")
        self.async_run_write_to_opc(self.motor_save_node, False)

    @pyqtSlot(int, int)
    def device_status_update(self, node, data_val):
        label_str = self.server_ns.read_label_node_structure(node)
        if data_val == True:
            getattr(self, label_str[0]).setStyleSheet(
                    "font: 15pt 'Webdings';color:rgb(85, 255, 0);")
        else:
            getattr(self, label_str[0]).setStyleSheet(
                    "font: 15pt 'Webdings';color:rgb(255, 0, 0);")

    @pyqtSlot(int, str)
    def oee_time_update(self, node_id:int, duration_str:str):
        label_str = self.server_ns.read_label_node_structure(node_id)
        self.label_updater(label_str, duration_str)


    @pyqtSlot(int, int)
    def module_status_update(self, node, data_value):
        label_list = self.server_ns.read_label_node_structure(node)
        label_object = getattr(self, label_list[0])
        module_number = self.check_module_number(label_list[0])
        module_label_object = getattr(self, f"module_{module_number}_label")
        module_check_box_object = getattr(self, f"module_{module_number}_check_box")
        module_check_box_object.setChecked(False)
        module_label_object.setStyleSheet(f"background-color: rgb({self.rgb_input_tuple[1]});color: rgb(0, 0, 0);")
        
        if data_value == 0: 
            label_object.setText("IDLE")
            #self.logger_handler(
            #        'INFO', f"Module {i+1} has Stopped")
            self.logger_handler('INFO', f"Module {module_number} is Idling")
        elif data_value == 1000:
            label_object.setText("DISABLED")
            module_check_box_object.setChecked(True)
            module_label_object.setStyleSheet(f"background-color: rgb({self.rgb_output_tuple[1]});color: rgb(0, 0, 0);")
            self.logger_handler('INFO', f"Module {module_number} is Disabled")
        elif data_value == 2000:
            label_object.setText("INITIALIZING")
            self.logger_handler('INFO', f"Module {module_number} is Initializing")
        elif data_value == 3000:
            label_object.setText("INIT DONE")
            self.logger_handler('INFO', f"Module {module_number} has Initialized")
        elif data_value == 4000:
            label_object.setText("RUNNING")
            self.logger_handler('INFO', f"Module {module_number} is Operational")
        elif data_value == 5000:
            label_object.setText("ALARM")
            self.logger_handler('INFO', f"Alarm at Module {module_number}")
    
    def check_module_number(self, label_str):
        if 'module_1' in label_str:
            return 1
        if 'module_2' in label_str:
            return 2
        if 'module_3' in label_str:
            return 3
        if 'module_4' in label_str:
            return 4
        if 'module_5' in label_str:
            return 5
        if 'module_6' in label_str:
            return 6

    def lot_entry_save(self):
        operator_id_node = self.server_ns.lot_input_nodes[0]
        recipe_id_node = self.server_ns.lot_input_nodes[1]
        operator_id_input_object = self.server_ns.read_label_node_structure(operator_id_node)
        recipe_input_object = self.server_ns.read_label_node_structure(recipe_id_node)
        current_operator = getattr(self,operator_id_input_object[1]).text()
        current_recipe = getattr(self,recipe_input_object[1]).text()
        stored_recipe = self.async_run_read_from_opc(recipe_id_node)

        if current_recipe  or current_operator:    
            if current_recipe != stored_recipe:
                self.reset_lot_oee()

            self.op_recp_set_text(operator_id_input_object, recipe_input_object, current_operator, current_recipe)
        else:
            self.op_recp_set_text(operator_id_input_object, recipe_input_object, None, None)




    def op_recp_set_text(self, operator_id_input_object, recipe_input_object, current_operator, current_recipe):
        if current_operator != None or current_recipe != None:
            getattr(self,operator_id_input_object[0]).setText(current_operator)
            getattr(self,recipe_input_object[0]).setText(current_recipe)
        else:     
            getattr(self,operator_id_input_object[0]).setText('NA')
            getattr(self,recipe_input_object[0]).setText('NA')
        self.async_run_write_to_opc(self.server_ns.lot_input_nodes[0], current_operator)
        self.async_run_write_to_opc(self.server_ns.lot_input_nodes[1], current_recipe)
     

    def logger_handler(self, log_type: str, log_msg: str):
        """[summary]

        Args:
            log_type (str): choose either 'INFO' or 'ALARM'
            msg (str): message to show at text box
        """
        current_time = datetime.now()
        time = (current_time.strftime("%d-%m-%Y | %H:%M:%S.%f")).split('.')[0]

        if log_type == 'ALARM':
            msg = f"{time} | {log_type} | #{log_msg}"
            self.alarm_log_text_edit.appendPlainText(msg)
        elif log_type == 'INFO':
            msg = f"{time} | {log_type} | {log_msg}"
            self.event_log_text_edit.appendPlainText(msg)

    def uph_update_plot(self):
        current_value = [self.async_run_read_from_opc(node) for node in self.server_ns.uph_plot_node]
        for rect, h in zip(self.plot_bar, current_value):
            rect.set_height(h)
        if len(self.plot_text) != 0:
            for text in self.plot_text:
                text.set_visible(False)
        self.plot_text.clear()

        for i, v in enumerate(current_value):
            self.plot_text.append(self.MplWidget.canvas.ax.text(
                i - 0.3, v + 80, str(v), color='red', fontsize=10, rotation=90))
        self.MplWidget.canvas.ax.relim()
        self.MplWidget.canvas.ax.autoscale_view()
        self.MplWidget.canvas.draw()
            
    def async_run_wp_serial_pn_gen(self, namespace_index, track_number):
        self.selected_track_number = track_number
        unit_present, runner_count,wp_part_number,wp_dimension,bcr_1_status,bcr_2_status,wp_validation_status,wp_serial = asyncio.run(self.client_wp_serial_pn_gen(namespace_index, track_number))
        self.id_track_count.setText(runner_count)
        self.id_track_part_num.setText(wp_part_number)
        self.id_track_rc.setText(str(wp_dimension))
        self.id_track_status_conv("id_track_bcr1", bcr_1_status)
        self.id_track_status_conv("id_track_bcr2", bcr_2_status)
        self.id_track_status_conv("id_track_wp_validation", wp_validation_status)
        if unit_present == 0:
            wp_serial = "N/A"
        self.id_track_serial.setText(wp_serial)

    def id_track_status_conv(self, label_str, bcr_2_status):
        if bcr_2_status == 1:
            self.label_updater(label_str,"PASS")
        elif bcr_2_status == 2:
            self.label_updater(label_str,"FAIL")
        else:
            self.label_updater(label_str,"N/A")

    @pyqtSlot(int, int)
    def id_track_update(self, node_id, data_value):
        label_str = self.server_ns.read_label_node_structure(node_id)[0]
        track_number = label_str.split('_')[1]
        button_name = f"track_{track_number}_button"
        label_name = f"track_{track_number}_label"
        button_object = getattr(self,button_name)
        label_object = getattr(self,label_name)
        runner_count = self.async_run_read_from_opc(node_id+1)
        runner_count_str = byte_swap_method(runner_count)
        button_object.setText(runner_count_str)
        label_object.setText(runner_count_str)
        green_light_on = f"background-color: rgb({self.rgb_input_tuple[1]});color: rgb(0, 0, 0);"
        green_light_off = f"background-color: rgb({self.rgb_input_tuple[0]});color: rgb(0, 0, 0);"
        if data_value == 1:
            button_object.setStyleSheet(green_light_on)    
            label_object.setStyleSheet(green_light_on)    
        elif data_value == 0:
            button_object.setStyleSheet(green_light_off)
            label_object.setStyleSheet(green_light_off)  

    
    def machine_status_update(self):#, node_id, data_value):
        machine_state = [int(self.async_run_read_from_opc(node_id)) for node_id in self.server_ns.machine_status_node]
        try:
            machine_idx = machine_state.index(1)
        except:
            machine_idx = None

        if machine_idx != None:
            machine_status_node = self.server_ns.machine_status_node[machine_idx]
            machine_status_name = self.server_ns.read_name_node_structure(machine_status_node)
            self.machine_status_label.setText(machine_status_name)
            if machine_status_name == "RUNNING" and self.lot_start_datetime_label.text() != '0':
                start_date_time = f"{self.date_days_label.text()}/{self.date_month_label.text()}/{self.date_year_label.text()} {self.time_hours_label.text()}:{self.time_minutes_label.text()}"
                self.lot_start_datetime_label.setText(start_date_time)

        else:
            self.machine_status_label.setText("IDLE")


    @pyqtSlot(int, int)    
    def alarm_status_update(self, node_id, data_value):
        if node_id == self.server_ns.alarm_nodes[0]: 
            alarm_label = self.server_ns.read_label_node_structure(node_id)
            if data_value > 0:
                self.blinkingtimer.start(500)
                try:
                    message = self.server_ns.alarm_table[data_value]
                except:
                    message = "NO Description"
                alarm_message = f"{data_value}-{message}"  
                self.label_updater(alarm_label,alarm_message)
                self.logger_handler('ALARM', f"{data_value}-{alarm_message}")
            elif data_value == 0:
                self.blinkingtimer.stop()
                self.alarm_bliking_colour_scheme(None)
                self.alarm_state = False
                self.label_updater(alarm_label,"")
        elif node_id != self.server_ns.alarm_nodes[0] and data_value > 0:
            other_alarm_message = self.server_ns.alarm_table[data_value]
            self.logger_handler('ALARM', f"{data_value}-{other_alarm_message}")

    def alarm_blinking(self):
        self.alarm_state = not self.alarm_state
        self.alarm_bliking_colour_scheme(self.alarm_state)

    def alarm_bliking_colour_scheme(self, state):
        if state == None:
            # frame_5
            self.machine_status_title_label.setStyleSheet(self.default_font_colour)
            self.machine_status_label.setStyleSheet(self.default_font_colour)
            self.frame_5.setStyleSheet(self.default_bg_colour)

            # frame_9
            self.frame_9.setStyleSheet(self.white_bg)
            self.alarm_label_title.setStyleSheet("")
            self.alarm_label.setStyleSheet("")

        elif state == True:
            # frame_5
            self.machine_status_title_label.setStyleSheet(self.red_font_color)  # red
            self.machine_status_label.setStyleSheet(self.red_font_color)  # red
            self.frame_5.setStyleSheet(self.white_bg)  # white

            # frame_9
            self.frame_9.setStyleSheet(self.white_bg)
            self.alarm_label_title.setStyleSheet(self.red_font_color)
            self.alarm_label.setStyleSheet(self.red_font_color)

        elif state == False:
            # frame_5
            self.machine_status_title_label.setStyleSheet(self.white_font_color)  # white
            self.machine_status_label.setStyleSheet(self.white_font_color)  # white
            self.frame_5.setStyleSheet(self.red_bg)  # red

            # frame_9
            self.frame_9.setStyleSheet(self.red_bg)
            self.alarm_label_title.setStyleSheet(self.white_font_color)
            self.alarm_label.setStyleSheet(self.white_font_color)



    async def client_wp_serial_pn_gen(self, namespace_index, track_number):
        return await self.wp_serial_pn_gen(namespace_index, track_number)

    def async_run_read_from_opc(self, node_id):
        return asyncio.run(self.client_read_from_opc(node_id))

    def async_run_write_to_opc(self, node_id, data_value):
        asyncio.run(self.client_write_to_opc(node_id, data_value))

    async def client_read_from_opc(self, node_id):
        return await self.read_from_opc(node_id,2)
        
    async def client_write_to_opc(self, node_id, data_value):
        #data_type = self.server_ns.read_data_type_node_structure(node_id)
        await self.write_to_opc(node_id,2,data_value)

    @pyqtSlot(int)
    def encoder_label_update(self, node):
        label_str = self.server_ns.read_label_node_structure(node)
        #selected_motor = f"encoder_motor_{self.selected_motor}"
        label_name = self.server_ns.read_name_node_structure(node)
        if str(self.selected_motor) in label_name:
            data_value = self.async_run_read_from_opc(node)
            self.label_updater(label_str, data_value)

    @pyqtSlot(int, int)
    def input_label_update(self, node_id, data_value):
        label_list = self.server_ns.read_label_node_structure(node_id)
        for label in label_list:
            label_object = getattr(self, label)
            label_object.setStyleSheet(
                f"background-color: rgb({self.rgb_input_tuple[data_value]});color: rgb(0, 0, 0);")
        if node_id == 11003:
            self.emo_label.setVisible(not data_value)


    @pyqtSlot(int, int)
    def output_label_update(self, node_id, data_value):
        label_list = self.server_ns.read_label_node_structure(node_id)
        for label in label_list:
            label_object = getattr(self, label)
            label_object.setStyleSheet(
                f"background-color: rgb({self.rgb_output_tuple[data_value]});color: rgb(0, 0, 0);")

            

    @pyqtSlot(list, str)
    def label_updater(self, label_list:str, label_str:str):
        """update label or ui element

        Args:
            label_list (str): name of the said label of be update. Can accept list of labels/buttons
            label_str (str): the content to be updated into the label
        """
        if isinstance(label_list, list):
            for label in label_list:
                if label != 'None':
                    label_object = getattr(self,label)
                    label_object.setText(str(label_str))
        elif label_list != 'None':
            if ',' in label_list:
                label_split = label_list.split(',')
                for items in label_split:
                    label_object = getattr(self,items)
                    label_object.setText(str(label_str))
            else:    
                label_object = getattr(self, label_list)
                label_object.setText(str(label_str))

    def server_start(self):
        self.status_device_1.setStyleSheet(
                    "font: 15pt 'Webdings';color:rgb(85, 255, 0);")
        self.server_thread.start()

    def closeEvent(self, event):
        print(self.user_level)
        if self.user_level < 2:
            self.message_box_show("YOU HAVE NO ACCESSS TO EXIT!!")
            event.ignore()
        #if user access level is accepted, accept event to close the HMI. event.accept()
        #else event.ignore() hence not closeing the HMI
        elif self.user_level >= 2:
            #self.send_data_to_opc(0,'exit',None)  
            #self.exit_input.put('exit')  
            self.write_to_opc_client(self.server_ns.system_exit_node, False)     
            self.client_thread.exit()
            event.accept()
    
    
        self.server_thread.exit()
        event.accept()


    def reset_lot_oee(self):
        [self.async_run_write_to_opc(node_id, 0) for node_id in self.server_ns.server_variable_list if 'lot' in self.server_ns.read_name_node_structure(node_id)]
        [self.async_run_write_to_opc(node_id, '00:00:00') for node_id in self.server_ns.time_variable_list if 'lot' in self.server_ns.read_name_node_structure(node_id)]
        self.lot_start_datetime_label.setText('0')
        [self.label_updater(self.server_ns.read_label_node_structure(node_id),0) for node_id in self.server_ns.server_variable_list  if 'lot' in self.server_ns.read_name_node_structure(node_id)]
        [self.label_updater(self.server_ns.read_label_node_structure(node_id), '00:00:00') for node_id in self.server_ns.time_variable_list if 'lot' in self.server_ns.read_name_node_structure(node_id)]

    def reset_shift_oee(self):
        [self.async_run_write_to_opc(node_id, 0) for node_id in self.server_ns.server_variable_list if 'oee' in self.server_ns.read_name_node_structure(node_id)]
        [self.async_run_write_to_opc(node_id, '00:00:00') for node_id in self.server_ns.time_variable_list if 'oee' in self.server_ns.read_name_node_structure(node_id)]

        [self.label_updater(self.server_ns.read_label_node_structure(node_id),0) for node_id in self.server_ns.server_variable_list  if 'oee' in self.server_ns.read_name_node_structure(node_id)]
        [self.label_updater(self.server_ns.read_label_node_structure(node_id), '00:00:00') for node_id in self.server_ns.time_variable_list if 'oee' in self.server_ns.read_name_node_structure(node_id)]     
        


    @pyqtSlot(int)
    def internal_seconds(self, seconds_time):
        self.label_updater("time_seconds_label", f"{seconds_time:02}")

    @pyqtSlot(int)
    def internal_minutes(self, minutes_time):
        self.label_updater("time_minutes_label", f"{minutes_time:02}")
       
    @pyqtSlot(int)
    def internal_hours(self, hours_time):
        self.label_updater("time_hours_label", f"{hours_time:02}")
      
    @pyqtSlot(int)
    def internal_days(self, days_time):
        self.label_updater("date_days_label", f"{days_time:02}")
       
    @pyqtSlot(int)
    def internal_months(self, months_time):
        self.label_updater("date_month_label", f"{months_time:02}")
        
    @pyqtSlot(int)
    def internal_years(self, years_time):
        self.label_updater("date_year_label", f"{years_time:04}")
       
    def set_line_edit_validator(self, node_list, int_num):
        for node in node_list:
            label_list = self.server_ns.read_label_node_structure(node)
            label_object = getattr(self, label_list[0])
            label_object.setMaxLength(int_num)
            label_object.setValidator(self.int_validator)

    
    def motor_move_function(self, state_logic, node_state):
        go_node = [node_id for node_id in self.server_ns.motor_go_input_nodes if f'{self.selected_motor}' in self.server_ns.read_name_node_structure(node_id)][0]
        motor_logic_node = [node_id for node_id in self.server_ns.motor_state_input_nodes if f'{self.selected_motor}' in self.server_ns.read_name_node_structure(node_id)][0]
        if state_logic!= None:
            self.async_run_write_to_opc(motor_logic_node, state_logic)
        self.async_run_write_to_opc(go_node, node_state)

    def init_laser_properties(self, properties_dict):
        for node in properties_dict:
            label_str = self.server_ns.read_label_node_structure(node)
            if label_str != "None":
                data_value = self.server_ns.read_value_node_structure(node)
                self.label_updater(label_str, data_value)
      


    def laser_properties_save(self):
        for node in self.server_ns.laser_1_properties:
            label_name = self.server_ns.read_label_node_structure(node)
            if label_name != "None":
                lineedit_object = getattr(self,label_name[0])
                input_value = lineedit_object.text()
                input_value_int = int(input_value)
                self.async_run_write_to_opc(node, input_value_int)

        for node in self.server_ns.laser_2_properties:
            label_name = self.server_ns.read_label_node_structure(node)
            if label_name != "None":
                lineedit_object = getattr(self,label_name[0])
                input_value = lineedit_object.text()
                input_value_int = int(input_value)
                self.async_run_write_to_opc(node, input_value_int)
              
        self.message_box_show("Laser Recipe Saved!")




    def setupUi(self, MainFrame):
        super(Ui_MainWindow, self).setupUi(MainFrame)
        self.int_validator = QIntValidator()
        self.manual_encoder_pos_line_edit.setMaxLength(10)
        self.manual_encoder_pos_line_edit.setValidator(self.int_validator)
        
        # ------------bar graph initialization------------------
        self.MplWidget.canvas.plt.xticks(rotation=45)
        self.MplWidget.canvas.ax.spines['top'].set_visible(False)
        self.MplWidget.canvas.ax.spines['right'].set_visible(False)
        self.MplWidget.canvas.ax.set_axisbelow(True)
        self.MplWidget.canvas.ax.tick_params(axis='x', labelsize=8)
        self.MplWidget.canvas.ax.tick_params(axis='y', labelsize=6)
        self.MplWidget.canvas.ax.yaxis.grid(color='gray', linestyle='dashed')
        self.plot_bar = self.MplWidget.canvas.ax.bar(
            self.x, self.y, align='center', width=1, color=(0.2, 0.4, 0.6),  edgecolor='blue')
        self.MplWidget.canvas.draw()

        #-----------create alarm list from dictionary-----------------
        num_rows = len(self.alarm_table)
        # -----------create table from alarm list---------------------
        num_col = 2
        self.tableWidget.setColumnCount(num_col)
        self.tableWidget.setRowCount(num_rows)

        for i, (key, value) in enumerate(self.alarm_table.items()):
            self.tableWidget.setItem(i, 0, QTableWidgetItem(str(key)))
            self.tableWidget.setItem(
                i, 1, QTableWidgetItem(str(value).strip()))

        column_1 = QtWidgets.QTableWidgetItem('Alarm Code')
        column_2 = QtWidgets.QTableWidgetItem('Alarm Description')
        self.tableWidget.setHorizontalHeaderItem(0, column_1)
        self.tableWidget.setHorizontalHeaderItem(1, column_2)
        header = self.tableWidget.horizontalHeader()
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.ResizeToContents)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        
        #-------------Navigation Buttons-----------------------------
        self.main_page_button.clicked.connect(
            lambda: self.stackedWidget.setCurrentIndex(0))
        self.lot_entry_button.clicked.connect(
            lambda: self.stackedWidget.setCurrentIndex(1))
        self.lot_info_button.clicked.connect(
            lambda: self.stackedWidget.setCurrentIndex(2))
        self.event_log_button.clicked.connect(
            lambda: self.stackedWidget.setCurrentIndex(3))
        self.io_list_button.clicked.connect(
            lambda: self.stackedWidget.setCurrentIndex(4))
        self.io_module_button.clicked.connect(
            lambda: self.stackedWidget.setCurrentIndex(5))
        self.event_log_button.clicked.connect(
            lambda: self.log_tab_widget.setCurrentIndex(0))
        self.show_event_button.clicked.connect(
            lambda: self.stackedWidget.setCurrentIndex(3))
        self.show_event_button.clicked.connect(
            lambda: self.log_tab_widget.setCurrentIndex(1))
        self.show_event_button.clicked.connect(
            lambda: self.event_log_button.setChecked(True))
        self.main_motor_button.clicked.connect(
            lambda:self.stackedWidget.setCurrentIndex(6))
        self.station_button.clicked.connect(
            lambda: self.stackedWidget.setCurrentIndex(7))
        self.life_cycle_button.clicked.connect(
            lambda: self.stackedWidget.setCurrentIndex(9))
        self.settings_button.clicked.connect(
            lambda: self.stackedWidget.setCurrentIndex(11))
        self.settings_button.clicked.connect(
            lambda: self.settings_tab_widget.setCurrentIndex(0))
        self.main_laser_button.clicked.connect(
            lambda: self.stackedWidget.setCurrentIndex(8))

        self.program_exit_button.clicked.connect(self.system_exit)


        #-------------Sub_page Behaviour-----------------------------
        #----Home Page
        
        self.stackedWidget.setCurrentIndex(0)
        self.machine_start_button.pressed.connect(lambda: self.async_run_write_to_opc(12000, True))
        self.machine_start_button.released.connect(lambda: self.async_run_write_to_opc(12000, False))


        self.machine_stop_button.pressed.connect(lambda: self.async_run_write_to_opc(12001, True))
        self.machine_stop_button.released.connect(lambda: self.async_run_write_to_opc(12001, False))

        self.machine_reset_button.pressed.connect(lambda: self.async_run_write_to_opc(12002, True))
        self.machine_reset_button.released.connect(lambda: self.async_run_write_to_opc(12002, False))

        default_bg = f"background-color: rgb(119, 118, 123);color: rgb(255, 255, 255);"

        self.home_load_button.setStyleSheet(default_bg)
        self.done_load_button.setStyleSheet(default_bg)

        self.home_load_button.pressed.connect(lambda: self.async_run_write_to_opc(12007, True))
        self.home_load_button.pressed.connect(lambda: self.home_load_button.setStyleSheet(f"background-color: rgb({self.rgb_input_tuple[1]});color: rgb(0, 0, 0);"))
        self.home_load_button.released.connect(lambda: self.home_load_button.setDisabled(True))

        self.done_load_button.pressed.connect(lambda: self.async_run_write_to_opc(12007, False))
        self.done_load_button.pressed.connect(lambda: self.async_run_write_to_opc(12010, True))
        
        self.done_load_button.pressed.connect(lambda: self.home_load_button.setChecked(False))
        self.done_load_button.released.connect(lambda: self.async_run_write_to_opc(12010, False))
        self.done_load_button.released.connect(lambda: self.home_load_button.setStyleSheet(default_bg))
        self.done_load_button.released.connect(lambda: self.home_load_button.setDisabled(False))
        
        #----login
        self.user_restriction_setup(self.default_access_level)
        self.user_login_button.clicked.connect(self.user_login_show)
        self.user_login_button.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(0))
        self.user_login_button.clicked.connect(lambda: self.main_page_button.setChecked(True))
        self.user_logout_button.clicked.connect(lambda: self.user_restriction_setup(self.default_access_level))
        self.user_logout_button.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(0))
        self.user_logout_button.clicked.connect(lambda: self.main_page_button.setChecked(True))

        #----Lot Entry Page
        self.lot_entry_save_button.clicked.connect(self.lot_entry_save)

        #----Laser Page
        self.set_line_edit_validator(self.server_ns.laser_1_properties, 4)
        self.set_line_edit_validator(self.server_ns.laser_2_properties, 4)
        self.init_laser_properties(self.server_ns.laser_1_properties)
        self.init_laser_properties(self.server_ns.laser_2_properties)
        self.main_laser_save_button.clicked.connect(self.laser_properties_save)


        #-----io list page
        self.io_list_button.clicked.connect(lambda: self.input_stacked_widget.setCurrentIndex(0))
        self.io_list_button.clicked.connect(lambda: self.output_stacked_widget.setCurrentIndex(0))
        self.io_list_button.clicked.connect(lambda: self.input_page_1_button.setChecked(True))
        self.io_list_button.clicked.connect(lambda: self.output_page_1_button.setChecked(True))

        self.input_page_1_button.clicked.connect(lambda: self.input_stacked_widget.setCurrentIndex(0))
        self.input_page_2_button.clicked.connect(lambda: self.input_stacked_widget.setCurrentIndex(1))
        self.output_page_1_button.clicked.connect(lambda: self.output_stacked_widget.setCurrentIndex(0))
        self.output_page_2_button.clicked.connect(lambda: self.output_stacked_widget.setCurrentIndex(1))

        #-----IO module Page
        self.io_module_button.clicked.connect(lambda: self.stackedWidget.setCurrentIndex(5))
        self.io_module_button.clicked.connect(lambda:self.io_module_stacked_widget.setCurrentIndex(0))
        self.io_module_button.clicked.connect(lambda:self.io_module_page_1_button.setChecked(True))

        self.io_module_page_1_button.clicked.connect(
            lambda: self.io_module_stacked_widget.setCurrentIndex(0))
        self.io_module_page_2_button.clicked.connect(
            lambda: self.io_module_stacked_widget.setCurrentIndex(1))
        self.io_module_page_3_button.clicked.connect(
            lambda: self.io_module_stacked_widget.setCurrentIndex(2))
        self.io_module_page_4_button.clicked.connect(
            lambda: self.io_module_stacked_widget.setCurrentIndex(3))
        self.io_module_page_5_button.clicked.connect(
            lambda: self.io_module_stacked_widget.setCurrentIndex(4))
        self.io_module_page_6_button.clicked.connect(
            lambda: self.io_module_stacked_widget.setCurrentIndex(5))

        # ---------------io modules button--------------------------------------
        #Loader Vacuum
        self.io_module_button_y0512.pressed.connect(lambda: self.async_run_write_to_opc(12062, True))
        self.io_module_button_y0512.released.connect(lambda: self.async_run_write_to_opc(12062, False))
        self.io_module_button_y0513.pressed.connect(lambda: self.async_run_write_to_opc(12063,True))
        self.io_module_button_y0513.released.connect(lambda: self.async_run_write_to_opc(12063,False))
        
        #loading y-axis cylinder
        self.io_module_button_y0505.pressed.connect(lambda: self.async_run_write_to_opc(12055, True))
        self.io_module_button_y0505.released.connect(lambda: self.async_run_write_to_opc(12055, False))
        self.io_module_button_y0506.pressed.connect(lambda: self.async_run_write_to_opc(12056,True))
        self.io_module_button_y0506.released.connect(lambda: self.async_run_write_to_opc(12056,False))
        
        #loader z-axis cylinder
        self.io_module_button_y0507.pressed.connect(lambda: self.async_run_write_to_opc(12057, True))
        self.io_module_button_y0507.released.connect(lambda: self.async_run_write_to_opc(12057, False))
        self.io_module_button_y0508.pressed.connect(lambda: self.async_run_write_to_opc(12058,True))
        self.io_module_button_y0508.released.connect(lambda: self.async_run_write_to_opc(12058,False))
        

        #loader vertical arm cylinder
        self.io_module_button_y0509.pressed.connect(lambda: self.async_run_write_to_opc(12059, True))
        self.io_module_button_y0509.released.connect(lambda: self.async_run_write_to_opc(12059, False))
        self.io_module_button_y0510.pressed.connect(lambda: self.async_run_write_to_opc(12060,True))
        self.io_module_button_y0510.released.connect(lambda: self.async_run_write_to_opc(12060,False))

        #flipper cylinder
        self.io_module_button_y0700.pressed.connect(lambda: self.async_run_write_to_opc(12082, True))
        self.io_module_button_y0700.released.connect(lambda: self.async_run_write_to_opc(12082, False))
        self.io_module_button_y0701.pressed.connect(lambda: self.async_run_write_to_opc(12083,True))
        self.io_module_button_y0701.released.connect(lambda: self.async_run_write_to_opc(12083,False))
        
        #flipper gripper cylinder
        self.io_module_button_y0710.pressed.connect(lambda: self.async_run_write_to_opc(12092, True))
        self.io_module_button_y0710.released.connect(lambda: self.async_run_write_to_opc(12092, False))
        self.io_module_button_y0711.pressed.connect(lambda: self.async_run_write_to_opc(12093,True))
        self.io_module_button_y0711.released.connect(lambda: self.async_run_write_to_opc(12093,False))
        
        #indexer
        self.io_module_button_y0703.pressed.connect(lambda: self.async_run_write_to_opc(12085, True))
        self.io_module_button_y0703.released.connect(lambda: self.async_run_write_to_opc(12085, False))
        self.io_module_button_y0704.pressed.connect(lambda: self.async_run_write_to_opc(12086,True))
        self.io_module_button_y0704.released.connect(lambda: self.async_run_write_to_opc(12086,False))

        #rotator
        self.io_module_button_y0706.pressed.connect(lambda: self.async_run_write_to_opc(12088, True))
        self.io_module_button_y0706.released.connect(lambda: self.async_run_write_to_opc(12088, False))
        self.io_module_button_y0707.pressed.connect(lambda: self.async_run_write_to_opc(12089,True))
        self.io_module_button_y0707.released.connect(lambda: self.async_run_write_to_opc(12089,False))

        #reject y-axis cylinder
        self.io_module_button_y0708.pressed.connect(lambda: self.async_run_write_to_opc(12090, True))
        self.io_module_button_y0708.released.connect(lambda: self.async_run_write_to_opc(12090, False))
        self.io_module_button_y0709.pressed.connect(lambda: self.async_run_write_to_opc(12091,True))
        self.io_module_button_y0709.released.connect(lambda: self.async_run_write_to_opc(12091,False))

        #reject cylinder
        self.io_module_button_y0600.pressed.connect(lambda: self.async_run_write_to_opc(12066, True))
        self.io_module_button_y0600.released.connect(lambda: self.async_run_write_to_opc(12066, False))
        self.io_module_button_y0601.pressed.connect(lambda: self.async_run_write_to_opc(12067,True))
        self.io_module_button_y0601.released.connect(lambda: self.async_run_write_to_opc(12067,False))        
        
        #unloading vacuum
        self.io_module_button_y0607.pressed.connect(lambda: self.async_run_write_to_opc(12073, True))
        self.io_module_button_y0607.released.connect(lambda: self.async_run_write_to_opc(12073, False))
        self.io_module_button_y0608.pressed.connect(lambda: self.async_run_write_to_opc(12074,True))
        self.io_module_button_y0608.released.connect(lambda: self.async_run_write_to_opc(12074,False))

        #blower
        self.io_module_button_y0609.pressed.connect(lambda: self.async_run_write_to_opc(12075, True))
        self.io_module_button_y0609.released.connect(lambda: self.async_run_write_to_opc(12075, False))
        self.io_module_button_y0610.pressed.connect(lambda: self.async_run_write_to_opc(12076,True))
        self.io_module_button_y0610.released.connect(lambda: self.async_run_write_to_opc(12076,False))

        #unloading z-axis cylinder
        self.io_module_button_y0602.pressed.connect(lambda: self.async_run_write_to_opc(12068, True))
        self.io_module_button_y0602.released.connect(lambda: self.async_run_write_to_opc(12068, False))
        self.io_module_button_y0603.pressed.connect(lambda: self.async_run_write_to_opc(12069,True))
        self.io_module_button_y0603.released.connect(lambda: self.async_run_write_to_opc(12069,False))

        #unloading finger
        self.io_module_button_y0604.pressed.connect(lambda: self.async_run_write_to_opc(12070, True))
        self.io_module_button_y0604.released.connect(lambda: self.async_run_write_to_opc(12070, False))
        self.io_module_button_y0605.pressed.connect(lambda: self.async_run_write_to_opc(12071,True))
        self.io_module_button_y0605.released.connect(lambda: self.async_run_write_to_opc(12071,False))


        #-----Motor Page Button
        #self.main_motor_button.clicked.connect(self.main_motor_page_behaviour)
        self.main_motor_button.clicked.connect(lambda:self.motor_page_stacked_widget.setCurrentIndex(0))
        
        #self.main_motor_button.clicked.connect(lambda:self.update_encoder_pos_display('motor_1'))
        self.main_motor_button.clicked.connect(lambda:self.load_config_method(self.server_ns.motor_1_properties))
        self.main_motor_button.clicked.connect(lambda:self.module_1_motor_1_button.setChecked(True))
        self.main_motor_button.clicked.connect(lambda:self.motor_selection(1))
        self.main_motor_button.clicked.connect(lambda:self.main_motor_station_stacked_widget.setCurrentIndex(0))
        self.main_motor_button.clicked.connect(lambda:self.main_motor_control_stacked_widget.setCurrentIndex(0))

        self.module_1_motor_1_button.clicked.connect(
            lambda: self.motor_selection(1))
        self.module_1_motor_2_button.clicked.connect(
            lambda: self.motor_selection(2))
        self.module_2_motor_1_button.clicked.connect(
            lambda: self.motor_selection(3))
        self.module_2_motor_2_button.clicked.connect(
            lambda: self.motor_selection(4))
        self.module_4_motor_1_button.clicked.connect(
            lambda: self.motor_selection(6))
        

        self.main_motor_save_button.clicked.connect(self.save_motor_properties)
        self.main_motor_save_button.clicked.connect(lambda: self.save_config_method(getattr(self.server_ns,f"motor_{self.selected_motor}_properties")))

        self.set_line_edit_validator(self.server_ns.motor_1_properties,6)
        self.set_line_edit_validator(self.server_ns.motor_2_properties,6)
        self.set_line_edit_validator(self.server_ns.motor_3_properties,6)
        self.set_line_edit_validator(self.server_ns.motor_4_properties,6)
        self.set_line_edit_validator(self.server_ns.motor_6_properties,6)

        #----Motor Buttons
        # 10 = manual go, 20 = jog+, 21 = jog+, 22 = HS jog+, 23 = HS jog-, 24=home, 25=home offset



        self.manual_go_button.pressed.connect(lambda: self.motor_move_function(10, True))
        self.manual_go_button.released.connect(lambda: self.motor_move_function(None, False))

        self.manual_jog_plus_button.pressed.connect(lambda: self.motor_move_function(20, True))
        self.manual_jog_plus_button.released.connect(lambda: self.motor_move_function(None, False))

        self.manual_jog_minus_button.pressed.connect(lambda: self.motor_move_function(21, True))
        self.manual_jog_minus_button.released.connect(lambda: self.motor_move_function(None, False))

        self.high_speed_jog_plus_button.pressed.connect(lambda: self.motor_move_function(22, True))
        self.high_speed_jog_plus_button.released.connect(lambda: self.motor_move_function(None, False))

        self.high_speed_jog_minus_button.pressed.connect(lambda: self.motor_move_function(23, True))
        self.high_speed_jog_minus_button.released.connect(lambda: self.motor_move_function(None, False))

        self.main_motor_home_button.pressed.connect(lambda: self.motor_move_function(24, True))
        self.main_motor_home_button.released.connect(lambda: self.motor_move_function(None, False))

        self.main_motor_home_offset_button.pressed.connect(lambda: self.motor_move_function(25, True))
        self.main_motor_home_offset_button.released.connect(lambda: self.motor_move_function(None, False))

        #----Motor 1
        self.motor_1_pos_1_go_button.pressed.connect(lambda: self.motor_move_function(1, True))
        self.motor_1_pos_2_go_button.pressed.connect(lambda: self.motor_move_function(2, True))
        self.motor_1_pos_3_go_button.pressed.connect(lambda: self.motor_move_function(3, True))
        self.motor_1_pos_4_go_button.pressed.connect(lambda: self.motor_move_function(4, True))
        self.motor_1_pos_5_go_button.pressed.connect(lambda: self.motor_move_function(5, True))
        self.motor_1_pos_6_go_button.pressed.connect(lambda: self.motor_move_function(6, True))
        self.motor_1_pos_7_go_button.pressed.connect(lambda: self.motor_move_function(7, True))

        self.motor_1_pos_1_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_1_pos_2_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_1_pos_3_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_1_pos_4_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_1_pos_5_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_1_pos_6_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_1_pos_7_go_button.released.connect(lambda: self.motor_move_function(None, False))

        #----Motor 2

        self.motor_2_pos_1_go_button.pressed.connect(lambda: self.motor_move_function(1, True))
        self.motor_2_pos_2_go_button.pressed.connect(lambda: self.motor_move_function(2, True))

        self.motor_2_pos_1_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_2_pos_2_go_button.released.connect(lambda: self.motor_move_function(None, False))

        #----Motor 3

        self.motor_3_pos_1_go_button.pressed.connect(lambda: self.motor_move_function(1, True))
        self.motor_3_pos_2_go_button.pressed.connect(lambda: self.motor_move_function(2, True))
        self.motor_3_pos_3_go_button.pressed.connect(lambda: self.motor_move_function(3, True))
        self.motor_3_pos_4_go_button.pressed.connect(lambda: self.motor_move_function(4, True))
        self.motor_3_pos_5_go_button.pressed.connect(lambda: self.motor_move_function(5, True))
        self.motor_3_pos_6_go_button.pressed.connect(lambda: self.motor_move_function(6, True))
        self.motor_3_pos_7_go_button.pressed.connect(lambda: self.motor_move_function(7, True))

        self.motor_3_pos_1_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_3_pos_2_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_3_pos_3_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_3_pos_4_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_3_pos_5_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_3_pos_6_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_3_pos_7_go_button.released.connect(lambda: self.motor_move_function(None, False))

        #----Motor 4

        self.motor_4_pos_1_go_button.pressed.connect(lambda: self.motor_move_function(1, True))
        self.motor_4_pos_2_go_button.pressed.connect(lambda: self.motor_move_function(2, True))

        self.motor_4_pos_1_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_4_pos_2_go_button.released.connect(lambda: self.motor_move_function(None, False))

        #----Motor 6

        self.motor_6_pos_1_go_button.pressed.connect(lambda: self.motor_move_function(1, True))
        self.motor_6_pos_2_go_button.pressed.connect(lambda: self.motor_move_function(2, True))

        self.motor_6_pos_1_go_button.released.connect(lambda: self.motor_move_function(None, False))
        self.motor_6_pos_2_go_button.released.connect(lambda: self.motor_move_function(None, False))


        # ------------enabling/disabling module------------------------
        self.module_1_check_box.clicked.connect(
            lambda: self.async_run_write_to_opc(10060, self.module_1_check_box.isChecked()))
        self.module_2_check_box.clicked.connect(
            lambda: self.async_run_write_to_opc(10061, self.module_2_check_box.isChecked()))
        self.module_3_check_box.clicked.connect(
            lambda: self.async_run_write_to_opc(10062, self.module_3_check_box.isChecked()))
        self.module_4_check_box.clicked.connect(
            lambda: self.async_run_write_to_opc(10063, self.module_4_check_box.isChecked()))
        self.module_5_check_box.clicked.connect(
            lambda: self.async_run_write_to_opc(10064, self.module_5_check_box.isChecked()))
        self.module_6_check_box.clicked.connect(
            lambda: self.async_run_write_to_opc(10065, self.module_6_check_box.isChecked()))


        #-----Light Tower Settings
        self.light_tower_save_button.clicked.connect(lambda: self.save_config_method(self.server_ns.light_tower_list))
        self.light_tower_save_button.clicked.connect(lambda:self.logger_handler("INFO", "Light Tower Settings Changed"))
        self.light_tower_cancel_button.clicked.connect(lambda: self.load_config_method(self.server_ns.light_tower_list))
        #-----User credentials
        self.user_save_button.clicked.connect(self.change_password)
        self.user_access_save_button.clicked.connect(lambda: self.save_config_method(self.server_ns.user_access_settings))
        self.user_access_cancel_button.clicked.connect(lambda: self.load_config_method(self.server_ns.user_access_settings))
        #-----API
        self.api_save_button.clicked.connect(lambda: self.save_config_method(self.server_ns.api_config))
        self.api_save_button.clicked.connect(lambda:self.logger_handler("INFO", "API Settings Changed"))
        
        self.api_cancel_button.clicked.connect(lambda: self.load_config_method(self.server_ns.api_config))
        #-----ID Track
        self.track_1_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,1))
        self.track_2_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,2))
        self.track_3_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,3))
        self.track_4_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,4))
        self.track_5_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,5))
        self.track_6_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,6))
        self.track_7_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,7))
        self.track_8_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,8))
        self.track_9_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,9))
        self.track_10_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,10))
        self.track_11_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,11))
        self.track_12_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,12))
        self.track_13_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,13))
        self.track_14_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,14))
        self.track_15_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,15))
        self.track_16_button.clicked.connect(lambda: self.async_run_wp_serial_pn_gen(2,16))
        
        self.clear_track.pressed.connect(lambda: self.async_run_write_to_opc(self.server_ns.id_track_clear_nodes[self.selected_track_number-1], True))
        self.clear_track.clicked.connect(lambda:self.logger_handler("INFO", f"Data Cleared on ID Track {self.selected_track_number}"))
        self.clear_track.released.connect(lambda: self.async_run_write_to_opc(self.server_ns.id_track_clear_nodes[self.selected_track_number-1], False))
        self.clear_track_all.pressed.connect(lambda: [self.async_run_write_to_opc(node_id, True) for node_id in self.server_ns.id_track_clear_nodes])
        self.clear_track_all.clicked.connect(lambda:self.logger_handler("INFO", f"Data Cleared on ALL ID Track"))
        self.clear_track_all.released.connect(lambda: [self.async_run_write_to_opc(node_id, False) for node_id in self.server_ns.id_track_clear_nodes])
        self.clear_runner_count.pressed.connect(lambda: self.async_run_write_to_opc(12009, True))
        self.clear_runner_count.clicked.connect(lambda:self.logger_handler("INFO", "Runner Count Reset"))
        self.clear_runner_count.released.connect(lambda: self.async_run_write_to_opc(12009, False))
        
        #-----Reset Lot Oee Shift
        self.reset_lot_oee_button.clicked.connect(self.reset_lot_oee)
        self.reset_shift_oee_button.clicked.connect(self.reset_shift_oee)
        
        #----shift reset time
        self.shift_save_button.clicked.connect(lambda: [self.async_run_write_to_opc(node_id, (getattr(self, self.server_ns.read_label_node_structure(node_id)[0]).time()).toString("H:mm")) for node_id in self.server_ns.shift_start_time_node])
        self.shift_cancel_button.clicked.connect(self.load_shift_time)
        #----Clear Logs
        self.clear_logs_button.clicked.connect(lambda: self.alarm_log_text_edit.clear())
        self.clear_logs_button.clicked.connect(lambda: self.event_log_text_edit.clear())

        #----Door By Pass

        self.machine_door_by_pass_button.clicked.connect(lambda: self.async_run_write_to_opc(12004,self.machine_door_by_pass_button.isChecked()))

        #----Manual Mode

        self.machine_manual_mode_button.clicked.connect(lambda: self.async_run_write_to_opc(12003,self.machine_manual_mode_button.isChecked()))

        #----Dry Cycle

        self.machine_dry_cycle_button.clicked.connect(lambda: self.async_run_write_to_opc(12005,self.machine_dry_cycle_button.isChecked()))

        #----Bypass API

        self.bypass_api_button.clicked.connect(lambda: self.async_run_write_to_opc(10700,self.bypass_api_button.isChecked()))

        #----Export oee
        self.export_oee_button.clicked.connect(self.export_oee)

        #----Export logs
        self.export_logs_button.clicked.connect(self.export_logs)


    def message_box_show(self, message: str):
        """output a dialog message box in top of UI

        Args:
            message (str): message to output to text
        """
        mbox = QtWidgets.QDialog()
        mbox.ui = MessageBox()
        mbox.ui.setupUi(mbox)
        mbox.ui.plainTextEdit.appendPlainText(message)
        mbox.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        mbox.exec()

    def system_exit(self):
        self.async_run_write_to_opc(self.server_ns.system_exit_node, False)
        self.server_thread.exit()
        stdout.flush()
        exit()

    def restart_program(self):
        self.async_run_write_to_opc(self.server_ns.system_exit_node, False)
        self.client_thread.exit()
        stdout.flush()
        execl(executable, 'python', __file__, *argv[1:])    

    def closeEvent(self, event):
        # create a method to check user access level
        #if self.current_user_level != 'level_3':
        #    self.message_box_show("YOU HAVE NO ACCESSS TO EXIT!!")
        #    event.ignore()
        #if user access level is accepted, accept event to close the HMI. event.accept()
        #else event.ignore() hence not closeing the HMI
        #elif self.current_user_level == 'level_3' or self.current_user_level == 'level_2':
            #self.send_data_to_opc(0,'exit',None)  
            #self.exit_input.put('exit')  
        self.async_run_write_to_opc(self.server_ns.system_exit_node, False)     
        self.server_thread.exit()
        event.accept()

# -----------user control section------------------------------

    def user_login_show(self):
        dialog = QtWidgets.QDialog()
        dialog.ui = Dialog()
        dialog.ui.setupUi(dialog)
        dialog.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint | QtCore.Qt.WindowType.WindowStaysOnTopHint)
        dialog.exec()
        username_idx = dialog.ui.username_input.currentIndex()
        username = dialog.ui.username_input.currentText()
        password = dialog.ui.password_input.text()
        access_level = list(map(int,(self.async_run_read_from_opc(self.server_ns.user_access_settings[username_idx])).split(',')))
        stored_password = self.async_run_read_from_opc(self.server_ns.login_credentials_nodes[username_idx])
        #print(username_idx, password, access_level, stored_password)

        if password == '' or password != stored_password:
            self.message_box_show("Wrong Password")
            access_level = self.default_access_level
        elif password == stored_password:
            self.message_box_show("Login Successful")
            self.logger_handler('INFO', f"User {username} logged in")
            self.user_level = username_idx

        self.user_restriction_setup(access_level)

    def user_restriction_setup(self, access_level):
        self.main_page_button.setEnabled(bool(access_level[0]))
        self.lot_entry_button.setEnabled(bool(access_level[1]))
        self.lot_info_button.setEnabled(bool(access_level[2]))
        self.event_log_button.setEnabled(bool(access_level[3]))
        self.show_event_button.setEnabled(bool(access_level[3]))
        self.io_module_button.setEnabled(bool(access_level[4]))
        self.io_list_button.setEnabled(bool(access_level[5]))
        self.main_motor_button.setEnabled(bool(access_level[6]))
        self.station_button.setEnabled(bool(access_level[7]))
        self.life_cycle_button.setEnabled(bool(access_level[8]))
        self.settings_button.setEnabled(bool(access_level[9]))
        self.main_laser_button.setEnabled(bool(access_level[10]))
        if self.user_level == 2:
            self.user_access_page.setEnabled(True)
            self.set_motor_properties(self.server_ns.motor_1_properties, True)
            self.set_motor_properties(self.server_ns.motor_2_properties, True)
            self.set_motor_properties(self.server_ns.motor_3_properties, True)
            self.set_motor_properties(self.server_ns.motor_4_properties, True)
            self.set_motor_properties(self.server_ns.motor_6_properties, True)

        elif self.user_level == 1:
            #self.export_logs_button.setEnabled(True)
            #self.export_oee_button.setEnabled(True)
            self.user_access_page.setEnabled(False)
            self.set_motor_properties(self.server_ns.motor_1_properties, False)
            self.set_motor_properties(self.server_ns.motor_2_properties, False)
            self.set_motor_properties(self.server_ns.motor_3_properties, False)
            self.set_motor_properties(self.server_ns.motor_4_properties, False)
            self.set_motor_properties(self.server_ns.motor_6_properties, False)

        else:
            #self.export_logs_button.setEnabled(False)
            #self.export_oee_button.setEnabled(False)
            self.user_access_page.setEnabled(False)
            self.set_motor_properties(self.server_ns.motor_1_properties, False)
            self.set_motor_properties(self.server_ns.motor_2_properties, False)
            self.set_motor_properties(self.server_ns.motor_3_properties, False)
            self.set_motor_properties(self.server_ns.motor_4_properties, False)
            self.set_motor_properties(self.server_ns.motor_6_properties, False)

    def set_motor_properties(self, properties_dict, logic_state):
        return [getattr(self, self.server_ns.read_label_node_structure(node_id)[0]).setEnabled(logic_state) for node_id in properties_dict]

    #-----export log
    def export_logs_items(self):
        dialog = QtWidgets.QDialog()
        dialog.ui = ExportLogsDialog()
        dialog.ui.setupUi(dialog)
        dialog.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint |
                              QtCore.Qt.WindowType.WindowStaysOnTopHint)

        drive_letter_list = self.usb_list(dialog)

        dialog.exec()
        drive_letter_index = dialog.ui.usb_device_input.currentIndex()
        if drive_letter_index >= 0:
            choosen_export_device = drive_letter_list[drive_letter_index]
        else:
            choosen_export_device = None
        return choosen_export_device

    def export_logs(self):
        event_log_text = self.event_log_text_edit.toPlainText()
        alarm_log_text = self.alarm_log_text_edit.toPlainText()
        current_time = datetime.now()
        file_name = (current_time.strftime("%d%m%Y%H%M%S.%f")).split('.')[0]

        choosen_export_device = self.export_logs_items()
        #print(choosen_export_device)
        if choosen_export_device != None:# or choosen_export_device >= 0:
            event_file = open(
                f"{choosen_export_device}\\event_log_{file_name}.txt", "w+")
            event_file.write(event_log_text)
            event_file.close()

            alarm_file = open(
                f"{choosen_export_device}\\alarm_log_{file_name}.txt", "w+")
            alarm_file.write(alarm_log_text)
            alarm_file.close()

    #----export  oee

    def export_oee(self):
        
        dialog = QtWidgets.QDialog()
        dialog.ui = ExportOeeDialog()
        dialog.ui.setupUi(dialog)
        dialog.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint |
                              QtCore.Qt.WindowType.WindowStaysOnTopHint)

        drive_letter_list = self.usb_list(dialog)
        dialog.exec()

        drive_letter_index = dialog.ui.usb_device_input.currentIndex()
        if drive_letter_index >= 0:
            choosen_export_device = drive_letter_list[drive_letter_index]
            self.export_oee_csv(dialog, choosen_export_device)
      
    def export_oee_csv(self,dialog, choosen_export_device):
        temp_from_date = dialog.ui.dateEdit.date()
        temp_to_date = dialog.ui.dateEdit_2.date()

        from_date = temp_from_date.toPyDate()
        to_date = temp_to_date.toPyDate()

        from_date_str = from_date.strftime("%Y-%m-%d %H:%M")
        to_date_str = to_date.strftime("%Y-%m-%d %H:%M")

        from_date_name = from_date.strftime("%Y-%m-%d_%H-%M")
        to_date_name = to_date.strftime("%Y-%m-%d_%H-%M")

        conn = sqlite3.connect(self.database_file)
        conn_cursor = conn.cursor()
        selection_range = f"""SELECT * FROM oee_data WHERE datetime BETWEEN "{from_date_str}" AND "{to_date_str}";"""
        conn_cursor.execute(selection_range)
        with open(f'{choosen_export_device}\\oee_{from_date_name}_{to_date_name}.csv', 'w') as out_csv_file:
            csv_out = writer(out_csv_file)
            csv_out.writerow([d[0] for d in conn_cursor.description])
            for result in conn_cursor:
                csv_out.writerow(result)
        conn.close()

    #----get usb drive

    def usb_list(self, dialog):
        drive_dict = {}
        drive_letter_list = self.get_drives_list()
        for drive in drive_letter_list:
            drive_name = win32api.GetVolumeInformation(f"{drive[0]}:\\")
            drive_name = drive_name[0]
            drive_dict.update({drive: drive_name})

        for drive, drive_name in drive_dict.items():
            item = f"{drive} ({drive_name})"
            dialog.ui.usb_device_input.addItem(item)
        return drive_letter_list

    def get_drives_list(self, drive_types=(win32con.DRIVE_REMOVABLE,)):
        drives_str = GetLogicalDriveStrings()
        drives = [item for item in drives_str.split("\x00") if item]
        return [item[:2] for item in drives if drive_types is None or GetDriveType(item) in drive_types]       
  



def main():
    app = QtWidgets.QApplication(argv)
    main_window = Ui_MainWindow()
    main_window.setWindowFlags(QtCore.Qt.WindowType.FramelessWindowHint)# | QtCore.Qt.WindowType.WindowStaysOnTopHint)
    main_window.server_start()
    main_window.showFullScreen()
    exit(app.exec())

if __name__ == "__main__":
    main()
