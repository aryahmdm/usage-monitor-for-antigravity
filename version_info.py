# pyright: reportUndefinedVariable=false

VSVersionInfo(
    ffi=FixedFileInfo(
        filevers=(0, 1, 1, 0),
        prodvers=(0, 1, 1, 0),
        mask=0x3F,
        flags=0x0,
        OS=0x40004,          # VOS_NT_WINDOWS32
        fileType=0x1,        # VFT_APP
        subtype=0x0,
    ),
    kids=[
        StringFileInfo([
            StringTable(
                '040904B0',  # Lang: US English, Charset: Unicode
                [
                    StringStruct('CompanyName', 'Antigravity Monitor'),
                    StringStruct('FileDescription', 'Usage Monitor for Antigravity'),
                    StringStruct('FileVersion', '0.1.1.0'),
                    StringStruct('InternalName', 'UsageMonitorForAntigravity'),
                    StringStruct('OriginalFilename', 'UsageMonitorForAntigravity.exe'),
                    StringStruct('ProductName', 'Usage Monitor for Antigravity'),
                    StringStruct('ProductVersion', '0.1.1.0'),
                ],
            ),
        ]),
        VarFileInfo([VarStruct('Translation', [0x0409, 1200])]),
    ],
)
