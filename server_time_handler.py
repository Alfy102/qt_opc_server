from tabnanny import check
from data_handler import time_calculation
from subscriptions import SubUPHHandler as uph_class
from subscriptions import SubOeeTimehandler as oee_time_class
from subscriptions import SubOeeHistorizingHandler as oee_sql_class


class SubSecondsHandler(oee_time_class):
    def __init__(self,seconds_signal,namespace_index, oee_time_signal):
        super().__init__(namespace_index, oee_time_signal)
        self.seconds_signal = seconds_signal
        self.namespace_index = namespace_index

    async def datachange_notification(self, node, val, data):
            node_id = node.nodeid.Identifier
            self.seconds_signal.emit(val)
            machine_state = [int(await self.read_from_opc(node_id, self.namespace_index)) for node_id in self.server_ns.machine_status_node]
            await self.machine_running([self.server_ns.oee_time_node]) 
            await self.oee_time_calculation(machine_state)

class SubMinutesHandler(uph_class, oee_sql_class):
    def __init__(self, database_file, namespace_index,seconds_signal,label_update_signal,uph_update_signal,reset_lot_oee_signal):
        super().__init__(database_file, namespace_index, label_update_signal,uph_update_signal)
    
        #oee_sql_class().__init__()
        self.seconds_signal = seconds_signal
        self.namespace_index = namespace_index
        self.reset_lot_oee = reset_lot_oee_signal

    async def datachange_notification(self, node, val, data):
        node_id = node.nodeid.Identifier
        check_hour = await self.read_from_opc(self.server_ns.hours_node, self.namespace_index)  
        self.seconds_signal.emit(val)
        await self.uph_minute_calculation()
        day_start, night_start = await self.get_shift_time()
        if val == 0 or val == 30:
            await self.uph_30_minute_calculation(val) 
            recipe = await self.read_from_opc(self.server_ns.recipe_name, self.namespace_index)
            if recipe != 'None':
                await self.insert_into_table(recipe)
                self.remove_oldest_row(2000)
        if check_hour == 0 and val == 15:
            await self.uph_reset_time()
        if (check_hour == day_start[0] and val == day_start[1]) or (check_hour == night_start[0] and val == night_start[1]):
            self.reset_lot_oee.emit()



    async def get_shift_time(self):
        shift_time = [await self.read_from_opc(node_id, self.namespace_index) for node_id in self.server_ns.shift_start_time_node]
        shift_time_split = [list(map(int, shift_time_item.split(':'))) for shift_time_item in shift_time]
        day_start = shift_time_split[0]
        night_start = shift_time_split[1]
        return day_start, night_start

    async def uph_reset_time(self):
        for node_id in self.server_ns.uph_plot_node:
            await self.write_to_opc(node_id, self.namespace_index, 0)

class SubHoursHandler(object):
    def __init__(self,seconds_signal):
        self.seconds_signal = seconds_signal
    async def datachange_notification(self, node, val, data):
            node_id = node.nodeid.Identifier
            self.seconds_signal.emit(val)

class SubDaysHandler(object):
    def __init__(self,seconds_signal):
        self.seconds_signal = seconds_signal
    async def datachange_notification(self, node, val, data):
            node_id = node.nodeid.Identifier
            self.seconds_signal.emit(val)

class SubMonthsHandler(object):
    def __init__(self,seconds_signal):
        self.seconds_signal = seconds_signal
    async def datachange_notification(self, node, val, data):
            node_id = node.nodeid.Identifier
            self.seconds_signal.emit(val)

class SubYearsHandler(object):
    def __init__(self,seconds_signal):
        self.seconds_signal = seconds_signal
    async def datachange_notification(self, node, val, data):
            node_id = node.nodeid.Identifier
            self.seconds_signal.emit(val)


