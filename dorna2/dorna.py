import json
import random
import time
from dorna2.ws import WS
from dorna2.config import config
import logging
import logging.handlers
import copy


class Dorna(WS):
    """docstring for Dorna"""
    def __init__(self, config=config):
        super(Dorna, self).__init__()
        self.config = config
        # init logger
        self.logger = None

    def logger_setup(self, log_path="dorna.log", maxBytes=100000, backupCount=1):
        """Set up logging to log to rotating files and also console output."""
        formatter = logging.Formatter('%(asctime)s %(message)s')
        self.logger = logging.getLogger("dorna_log")
        self.logger.setLevel(logging.INFO)

        # rotating file handler
        fh = logging.handlers.RotatingFileHandler(log_path, maxBytes=maxBytes, backupCount=backupCount)
        fh.setFormatter(formatter)
        self.logger.addHandler(fh)

        # console handler
        ch = logging.StreamHandler()
        ch.setFormatter(formatter)
        self.logger.addHandler(ch)


    # last message received
    def recv(self):
        return copy.deepcopy(self._recv)

    
    def last_msg(self):
        return copy.deepcopy(self._recv)


    # last message sent
    def send(self):
        return copy.deepcopy(self._send)


    def last_cmd(self):
        return copy.deepcopy(self._send)


    def sys(self):
        return copy.deepcopy(self._sys)


    def union(self):
        return copy.deepcopy(self._sys)

    """
    return aggregate and all the messages in _msgs
    cmd, msgs, union
    """
    def track_cmd(self):
        # make a copy and rem
        _track = copy.deepcopy(self._track)
        del _track["id"]

        # create union
        union = {}
        for i in range(len(_track["msgs"])):
            union = {**union, **_track["msgs"][i]}
        return {** _track, "union": union}


    def connect(self, host="localhost", port=443, timeout=5):
        # close the connection first
        if not self.close(timeout):
            return False 

        # Check the connection
        if not self.server(host, port, timeout):
            return False

        # initialize
        for cmd in self.config["cmd_init"]:
            self.cmd(cmd, timeout=1)

        return True

    def log(self, msg, *args, **kwargs):
        # setup log
        if self.logger == None:
            self.logger_setup()

        # print log
        self.logger.info(msg, *args, **kwargs)
    
    def rand_id(self, thr_low=100, thr_high= 1000000):
        return random.randint(thr_low, thr_high)

    """
    complete: wait for the completion or not
    timeout: the maximum amount of time (seconds), the API waits for the command completion, 
                negative (e.g. -1): wait for the command completion or error
                0: no waiting
                positive: wait for maximum timeout seconds to complete the command
    msg: command in form of text or dict
    **kwargs: Other parameters associated to the play
    --------
    return a dictionary formed by the union of the messages associated to this command 
    """
    def play(self, timeout=-1, msg=None, **kwargs):
        self._track = {"id": None, "msgs": [], "cmd": {}} # init track 

        # find msg
        if msg:
            # text
            if type(msg) == str:
                msg = json.loads(msg)

            elif type(msg) == dict:
                msg = copy.deepcopy(msg)
            else:
                return self.track_cmd()

        else:
            msg = copy.deepcopy(kwargs)

        # check the id
        if "id" in msg and type(msg["id"]) == int and msg["id"] > 0:
            pass
        else:
            msg["id"] = self.rand_id(100, 1000000)


        # remove all the None keys
        _msg = copy.deepcopy(msg)
        for key in _msg:
            if _msg[key] == None:
                del msg[key]
        
        # set the tracking id
        self._track["cmd"] = copy.deepcopy(msg) 
        self._track["id"] =  msg["id"]
        
        # take a copy
        self._send = copy.deepcopy(msg)
        
        # write the message
        self.write(json.dumps(msg))

        start = time.time()
        while self._track["id"] == msg["id"]:            
            # positive timeout
            if timeout >=0 and time.time() >= start + timeout:
                break
            time.sleep(0.001)

        # finish tracking
        self._track["id"] = None
        return self.track_cmd()


    """
    # high level commands
    """

    """
    play a text file, where each line is a valid command, if a command is not valid, it will skip it and send the next one
    file: path to the script file
    timeout= if you want to wait for the completion of this block of scripts or not
        negative (-1): waits for its completion
        0: no wait
        positive: wait for maximum of timeout seconds
    --------
    return number valid commands that was sent  
    """
    def play_script(self, file="", timeout=-1):
        try:
            with open(file, 'r') as f:
                lines = f.readlines()
                for l in lines:
                    try:
                        self.play(timeout=0, msg=l)
                    except Exception as ex:
                        self.log(ex)
        except Exception as ex:
            self.log(ex)

        return self.sleep(0, timeout=timeout)

    def play_json(self, cmd='{}', timeout=-1):
        return self.play(timeout=timeout, msg=cmd)

    def play_dict(self, cmd={}, timeout=-1):
        return self.play(timeout=timeout, msg=cmd)

    """
    wait for a given patter in received signal
    """
    def wait(self, timeout=-1, **kwargs):
        # set wait dict
        self._ptrn["wait"] = copy.deepcopy(kwargs)
        # track
        if timeout >= 0:
            start = time.time()
            while time.time() <= start + timeout and self._ptrn["wait"]:
                time.sleep(0.001)
            self._ptrn["wait"] = None
        else:
            while self.ptrn:
                time.sleep(0.001)

        return copy.deepcopy(set( kwargs.items()) & set( self._ptrn["sys"].items()))
    
    """
    send a motion command
    """
    def _motion(self, method, **kwargs):
        cmd = {"cmd": method}
        
        if "pace" in kwargs:
            cmd = {**copy.deepcopy(cmd), **self.config["pace"][kwargs["pace"]][method]}
        cmd = {**copy.deepcopy(cmd), **kwargs}

        rtn = self.play(**cmd)

        # return stat
        try:
            return rtn["union"]["stat"]
        except:
            return False

    """
    return a dictionary based on keys
    if no *args is present it will return a copy of sys
    """        
    def get(self, *args):
        sys = self.sys()
        return [sys[k] for k in args]

    """
    return one value based on the key
    """
    def val(self, key):
        return self.get(key)[0]

    # It is a shorten version of play, 
    # set a parameter and wait for its reply from the controller
    def cmd(self, cmd, **kwargs):
        kwargs_clean = {k: v for k, v in kwargs.items() if v is not None}
        kwargs = {**{"cmd": cmd}, **kwargs_clean}
        return self.play(**kwargs)


    """
    send jmove, rmove, lmove, cmove command
    """
    def jmove(self, **kwargs):
        return self._motion("jmove", **kwargs)

    def rmove(self, **kwargs):
        return self._motion("rmove", **kwargs)        

    def lmove(self, **kwargs):
        return self._motion("lmove", **kwargs)

    def cmove(self, **kwargs):
        return self._motion("cmove", **kwargs)

    def _key_val_cmd(self, key, val, cmd, rtn_key, rtn_keys, **kwargs):
        # adjust key and kwargs
        if key != None and val != None:
            kwargs = {**{key:val}, **kwargs}

        # send
        rtn = self.cmd(cmd, **kwargs)
        
        # return
        try:
            if rtn_key:
                return rtn["union"][rtn_key]
            else:
                return [rtn["union"][k] for k in rtn_keys]
        except:
            return False
    
    def _track_cmd_stat(self):
        rtn = self.track_cmd()
        try:
            return rtn["union"]["stat"]
        except:
            return False
    """
    read output i, or turn it on or off
    output(0): return the value of the out0
    output(0,1): set the value of the out0 to 1
    output(): return the value of the outputs
    output(out0=1, out2=0): set the value of out0 to 1 and out2 to 0 

    return -> the value of one out or all outs
    """
    def output(self, index=None, val=None, **kwargs):
        key = None
        if index !=None:
            key = "out"+str(index)
        
        cmd = "output"
        rtn_key = key
        rtn_keys = ["out"+str(i) for i in range(16)]

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def get_all_output(self, **kwargs):
        return self.output(**kwargs)

    def get_output(self, index=None, **kwargs):
        return self.output(index=index, **kwargs)

    def set_output(self, index=None, val=None, queue=None, **kwargs):
        self.output(index=index, val=val, queue=queue, **kwargs)
        return self._track_cmd_stat()

    """
    read pwm, or set its parameters
    pwm(0): return the value of the pwm0
    pwm(0,1): set the value of the pwm0 to 1
    pwm(): return the value of the pwms
    pwm(pwm0=1, freq2=1): set the value of pwm0 to 1 and freq2 to 1

    return the value of pwm or all of them    
    """
    def pwm(self, index=None, val=None, **kwargs):
        key = None
        if index !=None:
            key = "pwm"+str(index)
        
        cmd = "pwm"
        rtn_key = key
        rtn_keys = ["pwm"+str(i) for i in range(5)]

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    """
    read freq, or set its parameters
    freq(0): return the value of the freq0
    freq(0,1): set the value of the freq0 to 1
    """
    def freq(self, index=None, val=None, **kwargs):
        key = None
        if index !=None:
            key = "freq"+str(index)
        
        cmd = "pwm"
        rtn_key = key
        rtn_keys = ["freq"+str(i) for i in range(5)]

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    """
    read duty, or set its parameters
    duty(0): return the value of the duty0
    duty(0,1): set the value of the duty0 to 1
    """
    def duty(self, index, val=None, **kwargs):
        key = None
        if index !=None:
            key = "duty"+str(index)
        
        cmd = "pwm"
        rtn_key = key
        rtn_keys = ["duty"+str(i) for i in range(5)]

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def get_pwm(self, index=None, **kwargs):
        return self.pwm(index=index, **kwargs)

    def get_freq(self, index=None, **kwargs):
        return self.freq(index=index, **kwargs)

    def get_duty(self, index=None, **kwargs):
        return self.duty(index=index, **kwargs) 

    def set_pwm(self, index=None, enable=None, queue=None, **kwargs):
        self.pwm(index=index, val=enable, queue=queue, **kwargs)
        return self._track_cmd_stat()

    def set_freq(self, index=None, freq=None, queue=None, **kwargs):
        self.freq(index=index, freq=freq, queue=queue, **kwargs)
        return self._track_cmd_stat()

    def set_duty(self, index=None, duty=None, queue=None, **kwargs):
        self.duty(index=index, duty=index, queue=queue, **kwargs)
        return self._track_cmd_stat()

    """
    read input
    """
    def input(self, index=None, **kwargs):
        key = None
        if index !=None:
            key = "in"+str(index)
        
        cmd = "input"
        rtn_key = key
        rtn_keys = ["in"+str(i) for i in range(16)]
        val = None

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def get_all_input(self, **kwargs):
        return self.input(**kwargs)

    def get_input(self, index=None, **kwargs):
        return self.input(index=index, **kwargs)

    """
    read adc
    """
    def adc(self, index=None, **kwargs):
        key = None
        if index !=None:
            key = "adc"+str(index)
        
        cmd = "adc"
        rtn_key = key
        rtn_keys = ["adc"+str(i) for i in range(5)]
        val = None

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def get_all_adc(self, **kwargs):
        return self.adc(**kwargs)

    def get_adc(self, index=None, **kwargs):
        return self.adc(index=index, **kwargs)
    
    """
    probe
    """
    def probe(self, index=None, val=None, **kwargs):
        key = None
        if index !=None:
            key = "in"+str(index)
        
        cmd = "probe"
        rtn_key = None
        rtn_keys = ["j"+str(i) for i in range(8)]

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    """
    iprobe
    return joint values in a list
    """
    def iprobe(self, index=None, val=None, **kwargs):
        key = None
        if index !=None:
            key = "in"+str(index)
        
        cmd = "iprobe"
        rtn_key = None
        rtn_keys = ["j"+str(i) for i in range(8)]

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    
    """
    send a halt command
    """
    def halt(self, accel=None, **kwargs):
        key = "accel"
        val = accel
        cmd = "halt"
        rtn_key = "stat"
        rtn_keys = None

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)


    """
    read alarm status, set or unset alarm
    """
    def alarm(self, val=None, **kwargs):
        key = "alarm"
        cmd = "alarm"
        rtn_key = key
        rtn_keys = None

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def get_alarm(self, **kwargs):
        return self.alarm(**kwargs)

    def set_alarm(self, enable=None, **kwargs):
        self.alarm(val=enable, **kwargs)
        return self._track_cmd_stat()

    """
    sleep the controller for certain amount of time (seconds)
    """
    def sleep(self, val=None, **kwargs):
        key = "time"
        cmd = "sleep"
        rtn_key = "stat"
        rtn_keys = None

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)
    
    """
    set the value of joints / and return their values in a dictionary

    [list]: return the joint values in a list format
    """
    def joint(self, index=None, val=None, **kwargs):
        # read the joints
        if not val and not kwargs:
            try:
                return self.val("j"+str(index))
            except:
                return [self.val("j"+str(k)) for k in range(8)]  

        key = None
        if index !=None:
            key = "j"+str(index)
        
        cmd = "joint"
        rtn_key = key
        rtn_keys = ["j"+str(i) for i in range(8)]

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def get_all_joint(self):
        return self.joint()

    def get_joint(self, index=None):
        return self.joint(index=index)

    def set_joint(self, index=None, val=None, **kwargs):
        self.joint(index=index, val=val, **kwargs)
        return self._track_cmd_stat()

    def pose(self, index=None):
        """
        Get the robot x, y, z, a, b, c, d and e poses. 

        Returns:
            (list of length 8): The robot pose.
        """
        _pose = self.get("x", "y", "z", "a", "b", "c", "d", "e")
        try:
            return _pose[index]
        except:
            return _pose

    def get_all_pose(self):
        return self.pose()    

    def get_pose(self, index=None):
        return self.pose(index=index)


    def motor(self, val=None, **kwargs):
        """
        Enable or disable the robot motors. Or get the motor status (disabled or enabled).
        If the val parameter is not specified, then we get the motor status. 

        Parameters:
            val (int): Use this parameter to enable (val=1) or disable (val=1) the motors. 

        Returns:
            (int): The status of the motors.
        """
        key = "motor"
        cmd = "motor"
        rtn_key = key
        rtn_keys = None

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def get_motor(self, **kwargs):
        return self.motor(**kwargs)

    def set_motor(self, enable=None, **kwargs):
        self.motor(val=enable, **kwargs)
        return self._track_cmd_stat()

    def toollength(self, val=None, **kwargs):
        """
        Set and get the robot tool length. 
        If the length of the toollength is not specified then, we get the value of the toollength.

        Parameters:
            val (float or None): The length of the toollength in mm.

        Returns:
            (float): The robot toollength in mm.
        """
        key = "toollength"
        cmd = "toollength"
        rtn_key = key
        rtn_keys = None

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def get_toollength(self, **kwargs):
        return self.toollength(**kwargs)

    def set_toollength(self, length=None ,**kwargs):
        self.toollength(val=length, **kwargs)
        return self._track_cmd_stat()

    def version(self, **kwargs):
        """
        Get the version of the firmware running on the controller.

        Parameters:

        Returns:
            (int): The version of the firmware.
        """
        key = None
        val = None
        cmd = "version"
        rtn_key = "version"
        rtn_keys = None

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)


    def uid(self, **kwargs):
        """
        Get the controller UID number.

        Parameters:

        Returns:
            (str): The uid of the controller.
        """
        key = None
        val = None
        cmd = "uid"
        rtn_key = "uid"
        rtn_keys = None

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def gravity(self, **kwargs):
        key = None
        val = None        
        cmd = "gravity"
        rtn_key = key
        rtn_keys = ["gravity", "m", "x", "y", "z"]

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def get_gravity(self, **kwargs):
        return self.gravity(**kwargs)

    def set_gravity(self, enable=None, mass=None, x=None, y=None, z=None, **kwargs):
        self.gravity(gravity=enable, m=mass, x=x, y=y, z=z, **kwargs)
        return self._track_cmd_stat()

    def axis(self, index=None, val=None, **kwargs):
        key = None
        if index !=None:
            key = "ratio"+str(int(index))
        
        cmd = "axis"
        rtn_key = key
        rtn_keys = ["ratio"+str(i) for i in range(5,8)]

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def get_axis(self, index=None, **kwargs):
        return self.axis(index=index, **kwargs)

    def set_axis(self, index=None, ratio=None, **kwargs):
        self.axis(index=index, val=ratio, **kwargs)
        return self._track_cmd_stat()

    def get_axis_ratio(self, index=None, **kwargs):
        return self.axis(index=index, **kwargs)

    def set_axis_ratio(self, index=None, ratio=None,  **kwargs):
        self.axis(index=index, val=ratio, **kwargs)
        return self._track_cmd_stat()

    def get_axis(self, index=None, **kwargs):
        return_keys = [key+str(int(index)) for key in ["usem", "usee", "pprm", "tprm", "ppre", "tpre"]]
        return self._key_val_cmd(None, None, "axis", None, return_keys, **kwargs)

    def set_axis(self, index=None, usem=None, usee=None, pprm=None, tprm=None, ppre=None, tpre=None, **kwargs):
        return_keys = [key+str(int(index)) for key in ["usem", "usee", "pprm", "tprm", "ppre", "tpre"]]
        key_value = {k: v for k, v in zip(return_keys, [usem, usee, pprm, tprm, ppre, tpre])}
        self._key_val_cmd(None, None, "axis", None, return_keys, **key_value, **kwargs)
        return self._track_cmd_stat()

    def pid(self, index, **kwargs):
        key = None
        val = None        
        cmd = "pid"
        rtn_key = None
        rtn_keys = [prm+str(int(index)) for prm in ["p", "i", "d"]]

        return self._key_val_cmd(key, val, cmd, rtn_key, rtn_keys, **kwargs)

    def get_pid(self, index=None, **kwargs):
        return self.pid(index, **kwargs)

    def set_pid(self, index=None, p=None, i=None, d=None, **kwargs):
        self.pid(index=index, **{"p"+str(int(index)): p, "i"+str(int(index)): i, "d"+str(int(index)): d})
        return self._track_cmd_stat()

    def reset_pid(self, **kwargs):
        return self.set_pid(threshold=75, duration=3000, **kwargs)

    def get_err_thr(self, **kwargs):
        return self._key_val_cmd(None, None, "pid", "threshold", None, **kwargs)

    def set_err_thr(self, threshold=None, **kwargs):
        self._key_val_cmd("threshold", threshold, "pid", "threshold", None, **kwargs)
        return self._track_cmd_stat()

    def get_err_dur(self, **kwargs):
        return self._key_val_cmd(None, None, "pid", "duration", None, **kwargs)

    def set_err_dur(self, duration=None, **kwargs):
        self._key_val_cmd("duration", duration, "pid", "duration", None, **kwargs)
        return self._track_cmd_stat()

    def get_err(self, **kwargs):
        return self._key_val_cmd(None, None, "pid", None, ["threshold", "duration"], **kwargs)

    def set_err(self, thr=None, dur=None, **kwargs):
        self._key_val_cmd(None, None, "pid", None, ["threshold", "duration"], threshold=thr, duration=dur)
        return self._track_cmd_stat()

    def set_emergency(self, enable=False, key="in0", value=1):
        self._emergency = {"enable":enable, "key":key, "value":value}
