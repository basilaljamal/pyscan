import time
from itertools import count
from epics import PV


def convert_to_list(value):
    """
    If the input parameter is not a list, convert to one.
    :return: The value in a list, or None.
    """
    return [value] if (value is not None) and (not isinstance(value, list)) else value


def convert_to_position_list(axis_list):
    """
    # Change the PER KNOB to PER INDEX of positions.
    :param axis_list: PER KNOB list of positions.
    :return: PER INDEX list of positions.
    """
    return [list(positions) for positions in zip(*axis_list)]


def connect_to_pv(pv_name, n_connection_attempts=3):
    """
    Start a connection to a PV.
    :param pv_name: PV name to connect to.
    :param n_connection_attempts: How many times you should try to connect before raising an exception.
    :return: PV object.
    :raises ValueError if cannot connect to PV.
    """
    pv = PV(pv_name, auto_monitor=False)
    for i in range(n_connection_attempts):
        if pv.connect():
            return pv
        time.sleep(0.1)

    raise ValueError("Cannot connect to PV '%s'." % pv_name)


class EpicsWriter(object):
    """
    Sequentially write the PV value and wait for the PV to reach the desired value.
    """

    def __init__(self, list_of_pvs):
        self.pvs = [connect_to_pv(pv_name) for pv_name in convert_to_list(list_of_pvs)]

    def write(self, values, tolerance=0.00001, timeout=5):
        """
        Write values and wait for PVs to reach set value.
        :param values: Values to set.
        :param tolerance: Tolerance that needs to be reached.
        :param timeout: Timeout to reach the desired position.
        :raise ValueError if position cannot be reached in time
        """
        values = convert_to_list(values)

        for pv, value in zip(self.pvs, values):
            pv.put(value)

        # Boolean array to represent which PVs have reached their target value.s
        within_tolerance = [False] * len(self.pvs)
        initial_timestamp = time.time()

        # Read values until all PVs have reached the desired value or time has run out.
        while not all(within_tolerance) and time.time() - initial_timestamp < timeout:
            for index, pv in ((index, pv) for index, reached, pv
                              in zip(count(), within_tolerance, self.pvs) if not reached):
                # The get method might return a None. In this case we do not care about the method.
                current_value = pv.get()
                if not current_value:
                    continue

                if abs(pv.get() - values[index]) < tolerance:
                    within_tolerance[index] = True

        if not all(within_tolerance):
            raise ValueError("Cannot achieve position in specified time.")

    def close(self):
        for pv in self.pvs:
            pv.disconnect()


class EpicsReader(object):
    """
    Sequentially read the PVs and return a list of results.
    """

    # TODO: Check for first time connection speed.
    def __init__(self, list_of_pvs, n_measurments=1):
        self.pvs = [connect_to_pv(pv_name) for pv_name in convert_to_list(list_of_pvs)]
        self.n_measurments = n_measurments

    def read(self):
        """
        Read PVs one by one.
        :return: List of results.
        """
        result = []
        for pv in self.pvs:
            if self.n_measurments == 1:
                result.append(pv.get())
            else:
                pv_result = []
                for i in range(self.n_measurments):
                    pv_result.append(pv.get())
                result.append(pv_result)

        return result

    def close(self):
        for pv in self.pvs:
            pv.disconnect()


class SimpleExecuter(object):
    """
    Execute all callbacks in the same thread.
    Each callback method should accept 2 parameters: position, sampled values.
    """

    def __init__(self, callbacks):
        self.callbacks = callbacks

    def execute(self, context):
        for callback in self.callbacks:
            callback(context["position"], context["value"])


class SimpleDataProcessor(object):
    """
    Save the position and the received data at this position.
    """

    def __init__(self):
        self.positions = []
        self.data = []

    def process(self, position, data):
        self.positions.append(position)
        self.data.append(data)

    def get_data(self):
        return [(position, data) for position, data in zip(self.positions, self.data)]
