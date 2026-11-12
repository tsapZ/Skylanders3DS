"""apply_cps_nop.py <azahar checkout>: ARM-mode CPS as a no-op in Azahar's dynarmic, as its Thumb CPS already is.

Trap Team 3DS stopped at once (Azahar rates it "Won't boot"): at pc 0x0048271C it runs 0xF10C0040, CPSID f, which
dynarmic translates by asking for the interpreter (arm_CPS -> InterpretThisInstruction), and Azahar has none: its
InterpreterFallback is UNREACHABLE (log: "InterpeterFallback reached with pc = 0x0048271c, code = 0xf10c0040").
3DS programs run in user mode, where CPS changes nothing (the ARM ARM: CPS in User mode is a NOP), so translating it
as nothing is what the hardware does. dynarmic's thumb16_CPS already returns true the same way. The edit is checked
before it is written; a second run changes nothing. dynarmic is 0BSD. Stdlib only."""
import pathlib
import sys

root = pathlib.Path(sys.argv[1])
path = root / "externals/dynarmic/src/dynarmic/frontend/A32/translate/impl/status_register_access.cpp"
OLD = "bool TranslatorVisitor::arm_CPS() {\n    return InterpretThisInstruction();\n}"
NEW = ("bool TranslatorVisitor::arm_CPS() {\n"
       "    // A no-op, as thumb16_CPS: 3DS programs run in user mode, where CPS changes nothing, and Azahar has no\n"
       "    // interpreter to fall back to (Skylanders Trap Team 3DS runs CPSID f at boot).\n"
       "    return true;\n"
       "}")
raw = path.read_bytes().decode("utf-8")
crlf = "\r\n" in raw
text = raw.replace("\r\n", "\n")
if NEW in text:
    print("already applied")
    sys.exit(0)
if text.count(OLD) != 1:
    print("arm_CPS not found as expected; nothing changed")
    sys.exit(1)
text = text.replace(OLD, NEW)
path.write_bytes((text.replace("\n", "\r\n") if crlf else text).encode("utf-8"))
print("applied:", path)
