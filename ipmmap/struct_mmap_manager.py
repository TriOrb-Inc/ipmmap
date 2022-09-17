"""メモリマップファイル管理クラス(struct)
"""

import time
import pathlib
import importlib
import mmap
import ctypes
from typing import Any

from .mmap_manager import AbstractMmapManger, DEFAULT_MMAP_FILE_DIR, DEFAULT_FASTENERS_FILE_DIR
from .struct import base_struct
from .exception import ipmmap_error as Err 


class BaseStructMmapManager(AbstractMmapManger):
    """Base class for StructMmapReader, Editor and Manager

    Args:
        AbstractMmapManger (_type_): _description_

    Raises:
        Err.StructNotFoundIpMmapError: _description_

    Returns:
        _type_: _description_
    """

    @staticmethod
    def setUserStructs(moduleNameList):
        for name in moduleNameList:
            importlib.import_module(name)

    def __init__(self, structName: str, tag: str="", mmapDir: pathlib.Path=None, fastenerDir: pathlib.Path=None):
        super().__init__(mmapDir, fastenerDir)
        self.structType = self._searchStructType(structName)
        fileName = "{}_{}".format(self.structType.__name__, tag)
        self.mmapFilePath = (self._getUseFDir(DEFAULT_MMAP_FILE_DIR, mmapDir) / fileName).with_suffix('.mmap').resolve()
        self.fastenerFilePath = (self._getUseFDir(DEFAULT_FASTENERS_FILE_DIR, fastenerDir) / fileName).with_suffix('.lockfile').resolve()


    # search IPMMAP Structure of user deinition
    def _searchStructType(self, structName: str):
        for st in base_struct.BaseMmapStructure.__subclasses__():
            if structName == st.__name__:
                return st

        raise Err.StructNotFoundIpMmapError(structName)

    def _generateStruct(self):
        return self.structType(base_struct.MmapStructureHeader(0x1128, time.time()))

    def _createNewMmapFile(self, dataStruct):
        try:
            with open(self.mmapFilePath, "wb") as fs:
                fs.write(dataStruct)
        except Exception as e: 
            pass


    # 最終更新時刻取得関数
    def getLastUpdate(self) -> float:
        """Returns last update time of IPMMAP's shared memory as the UNIX epoch time (float).
        This time can edit only DataStructMmapEditor.updateLastUpdate().
        the default value is 0.

        Returns:
            float: UNIX epoch time
        """
        if not self.mm is None:
            self.mm.seek(0)
            mmData = self.structType.from_buffer_copy(self.mm)
            return mmData.header.time_stamp
        else:
            return -1


# 読み出し専用クラス
class DataStructMmapReader(BaseStructMmapManager):
    def __init__(self, structName: str, tag: str="", mmapDir: pathlib.Path=None, fastenerDir: pathlib.Path=None):
        super().__init__(structName, tag, mmapDir, fastenerDir)
        self.editable = False

        # mmapオブジェクトを取得

    def readData(self, key: str) -> any:
        """Returns a value of designated a key-string any IPMMAP Structure's fields. 

        Args:
            key (str): string of a IPMMAP Structure's field name

        Returns:
            any: value
        """
        self.mm.seek(0)
        mmData = self.structType.from_buffer_copy(self.mm)

        val = mmData
        for k in key.split('.'):
            val = getattr(val, k)

        return val

    def readMappedBuffer(self):
        mmData = None
        if not self.mm is None:
            self.mm.seek(0)
            mmData = self.structType.from_buffer_copy(self.mm)
        return mmData

# 編集クラス
class DataStructMmapEditor(DataStructMmapReader):

    def __init__(self, structName: str, tag: str="", mmapDir: pathlib.Path=None, fastenerDir: pathlib.Path=None):
        super().__init__(structName, tag, mmapDir, fastenerDir)
        self.editable = True

    # 最終更新時刻更新関数
    def updateLastUpdate(self) -> None:
        """Update last update time of IPMMAP's shared memory.
        """
        if not self.mm is None:
            self.mm.seek(0)
            mmData = self.structType.from_buffer(self.mm)
            mmData.header.time_stamp = time.time()

        return

    def writeData(self, key: str, value: Any) -> None:
        """Set a value of designated a key-string any IPMMAP Structure's fields

        Args:
            key (str): string of a IPMMAP Structure's field name
            value (Any): value to write for IPMMAP's shared memory space
        """
        if not self.mm is None:
            self.mm.seek(0)
            mmData = self.structType.from_buffer(self.mm)

            keyList = key.split('.')

            # set recursive
            attr = mmData
            for k in keyList[:-1]:
                attr = getattr(attr, k)
                
            setattr(attr, keyList[-1], value)

        return

    def referMappedBuffer(self):
        if not self.mm is None:
            self.mm.seek(0)
            return self.structType.from_buffer(self.mm)
        else:
            return None   

    def clearMappedBuffer(self) -> None:
        if not self.mm is None:
            self.mm.seek(0)
            mmData = self.structType.from_buffer(self.mm)
            ctypes.memset(ctypes.byref(mmData), 0, ctypes.sizeof(mmData))

        return None


# 管理クラス（新規作成権限あり）
class DataStructMmapManager(DataStructMmapEditor):

    def __init__(self, structName: str, tag: str="", mmapDir: pathlib.Path=None, fastenerDir: pathlib.Path=None, 
                 create: bool=False, force: bool=False):
        super().__init__(structName, tag, mmapDir, fastenerDir)
        self.editable = True

        # create new mmap
        if create:
            # if "force" mode, old mmapfile is overwritten 
            if force or (not self.mmapFilePath.exists()):
                self._createNewMmapFile(self._generateStruct())
                # print("file generated: ", self.mmapFilePath)
            else:
                pass
                # print("file already exist")


    def openMemory(self):
        self.fs_master = open(self.mmapFilePath, 'r+b')
        self.mm_master = mmap.mmap(self.fs_master.fileno(), 0, access=mmap.ACCESS_DEFAULT)

    
    def closeMemory(self):
        if (not self.mm_master is None) and (not self.mm_master.closed):
            self.mm_master.close()
            self.mm_master = None

        if (not self.fs_master is None):
            self.fs_master.close()


    