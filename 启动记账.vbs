' 简账启动器：用 pythonw 打开主程序，不显示控制台窗口
Dim fso, shell, base
Set fso = CreateObject("Scripting.FileSystemObject")
base = fso.GetParentFolderName(WScript.ScriptFullName)
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = base
shell.Run "pythonw.exe """ & base & "\main.py""", 0, False
