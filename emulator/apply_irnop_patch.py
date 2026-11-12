"""apply_irnop_patch.py <azahar checkout>: ir:USER's older receive path, for Spyro's Adventure 3DS (an older SDK).

Run after apply_portal_patch.py. Spyro's Adventure 3DS (tools/code_services.py on the owner's dump; its IR library's
wrappers read with llvm-objdump) starts infrared with InitializeIrNop (0x00010182) instead of InitializeIrNopShared,
with the same parameters (buffer sizes, packet counts, baud rate, the shared memory), and then takes every received
packet with ReceiveIrnop (0x000F0040: a static buffer, the payload only; its caller looks at the first byte for the
portal's reply letter) or, above 252 bytes, ReceiveIrnopLarge (0x00100042: a mapped buffer). Both answer the payload's
size and how many packets still wait (the game reads again while that is above zero). It sends with SendIrNop or, above
252 bytes, SendIrNopLarge (0x000E0042: a mapped buffer). Azahar had none of the four (nullptr in the function table).
Here InitializeIrNop is InitializeIrNopShared plus a mode in which received payloads wait in a queue for ReceiveIrnop
instead of going into the shared memory's receive buffer; an empty queue answers an error (NoData), which the game
takes as "nothing". Giants, Swap Force, Trap Team and SuperChargers Racing call InitializeIrNopShared and stay as
they were. All edits are checked before anything is written; a second run changes nothing. Part of Azahar (GPLv2 or
later). Stdlib only."""
import pathlib
import sys

H_EDITS = [
    ("#include <functional>\n", "#include <deque>\n#include <functional>\n"),
    ("    void ReleaseReceivedData(Kernel::HLERequestContext& ctx);\n",
     "    void ReleaseReceivedData(Kernel::HLERequestContext& ctx);\n"
     "\n"
     "    /**\n"
     "     * InitializeIrNop service function (Skylanders Spyro's Adventure 3DS, an older SDK): the parameters of\n"
     "     * InitializeIrNopShared; the game then takes each received packet with ReceiveIrnop or ReceiveIrnopLarge\n"
     "     * instead of reading the shared memory's receive buffer.\n"
     "     */\n"
     "    void InitializeIrNop(Kernel::HLERequestContext& ctx);\n"
     "\n"
     "    /**\n"
     "     * ReceiveIrnop service function: the payload of the oldest received packet (InitializeIrNop mode).\n"
     "     *  Inputs:\n"
     "     *      1 : Size of the game's buffer (a static buffer, id 0)\n"
     "     *  Outputs:\n"
     "     *      1 : Result of function, 0 on success, NoData when nothing was received\n"
     "     *      2 : Size of the payload\n"
     "     *      3 : Packets still waiting after this one\n"
     "     *      4, 5 : Static buffer descriptor (id 0) and address: the payload\n"
     "     */\n"
     "    void ReceiveIrnop(Kernel::HLERequestContext& ctx);\n"
     "\n"
     "    /// ReceiveIrnopLarge service function: ReceiveIrnop into a mapped buffer (inputs 1 : size, 2, 3 : buffer).\n"
     "    void ReceiveIrnopLarge(Kernel::HLERequestContext& ctx);\n"
     "\n"
     "    /// SendIrNopLarge service function: SendIrNop from a mapped buffer (inputs 1 : size, 2, 3 : buffer).\n"
     "    void SendIrNopLarge(Kernel::HLERequestContext& ctx);\n"
     "\n"
     "    /// The oldest received payload, cut to max_size; waiting is how many are left after it.\n"
     "    std::vector<u8> TakeReceived(u32 max_size, u32& waiting);\n"),
    ("    IRDevice* active_device = nullptr;\n",
     "    IRDevice* active_device = nullptr;\n"
     "    // InitializeIrNop (Spyro's Adventure 3DS): received payloads wait here for ReceiveIrnop instead of going\n"
     "    // into the shared memory. Not serialized either.\n"
     "    bool receive_by_copy = false;\n"
     "    std::deque<std::vector<u8>> received_packets;\n"),
]

NEW_FUNCTIONS = """void IR_USER::InitializeIrNop(Kernel::HLERequestContext& ctx) {
    // The same parameters as InitializeIrNopShared (Spyro's Adventure 3DS: sizes, packet counts, baud rate and the
    // shared memory); only the way the game takes received packets differs.
    InitializeIrNopShared(ctx);
    receive_by_copy = true;
    LOG_INFO(Service_IR, "called (InitializeIrNop): received packets go to ReceiveIrnop");
}

std::vector<u8> IR_USER::TakeReceived(u32 max_size, u32& waiting) {
    std::vector<u8> data = std::move(received_packets.front());
    received_packets.pop_front();
    if (data.size() > max_size) {
        LOG_ERROR(Service_IR, "a packet of {} bytes cut to the game's {}", data.size(), max_size);
        data.resize(max_size);
    }
    waiting = static_cast<u32>(received_packets.size());
    return data;
}

void IR_USER::ReceiveIrnop(Kernel::HLERequestContext& ctx) {
    IPC::RequestParser rp(ctx);
    const u32 size = rp.Pop<u32>();
    if (received_packets.empty()) {
        IPC::RequestBuilder rb = rp.MakeBuilder(1, 0);
        rb.Push(Result(ErrorDescription::NoData, ErrorModule::IR, ErrorSummary::NotFound,
                       ErrorLevel::Status));
        return;
    }
    u32 waiting = 0;
    std::vector<u8> data = TakeReceived(size, waiting);
    const u32 data_size = static_cast<u32>(data.size());
    IPC::RequestBuilder rb = rp.MakeBuilder(3, 2);
    rb.Push(ResultSuccess);
    rb.Push(data_size);
    rb.Push(waiting);
    rb.PushStaticBuffer(std::move(data), 0);
    LOG_TRACE(Service_IR, "called, {} bytes, {} waiting", data_size, waiting);
}

void IR_USER::ReceiveIrnopLarge(Kernel::HLERequestContext& ctx) {
    IPC::RequestParser rp(ctx);
    const u32 size = rp.Pop<u32>();
    auto& buffer = rp.PopMappedBuffer();
    if (received_packets.empty()) {
        IPC::RequestBuilder rb = rp.MakeBuilder(1, 2);
        rb.Push(Result(ErrorDescription::NoData, ErrorModule::IR, ErrorSummary::NotFound,
                       ErrorLevel::Status));
        rb.PushMappedBuffer(buffer);
        return;
    }
    u32 waiting = 0;
    const std::vector<u8> data = TakeReceived(size, waiting);
    buffer.Write(data.data(), 0, data.size());
    IPC::RequestBuilder rb = rp.MakeBuilder(3, 2);
    rb.Push(ResultSuccess);
    rb.Push(static_cast<u32>(data.size()));
    rb.Push(waiting);
    rb.PushMappedBuffer(buffer);
    LOG_TRACE(Service_IR, "called, {} bytes, {} waiting", data.size(), waiting);
}

void IR_USER::SendIrNopLarge(Kernel::HLERequestContext& ctx) {
    IPC::RequestParser rp(ctx);
    const u32 size = rp.Pop<u32>();
    auto& buffer = rp.PopMappedBuffer();
    std::vector<u8> data(size);
    buffer.Read(data.data(), 0, size);

    IPC::RequestBuilder rb = rp.MakeBuilder(1, 2);
    if (connected_device) {
        ActiveDevice()->OnReceive(data);
        send_event->Signal();
        rb.Push(ResultSuccess);
    } else {
        LOG_ERROR(Service_IR, "not connected");
        rb.Push(Result(static_cast<ErrorDescription>(13), ErrorModule::IR,
                       ErrorSummary::InvalidState, ErrorLevel::Status));
    }
    rb.PushMappedBuffer(buffer);
    LOG_TRACE(Service_IR, "called, data={}", fmt::format("{:02x}", fmt::join(data, " ")));
}

void IR_USER::GetConnectionStatus(Kernel::HLERequestContext& ctx) {
"""

CPP_EDITS = [
    ("void IR_USER::PutToReceive(std::span<const u8> payload) {\n"
     "    LOG_TRACE(Service_IR, \"called, data={}\", fmt::format(\"{:02x}\", fmt::join(payload, \" \")));\n",
     "void IR_USER::PutToReceive(std::span<const u8> payload) {\n"
     "    LOG_TRACE(Service_IR, \"called, data={}\", fmt::format(\"{:02x}\", fmt::join(payload, \" \")));\n"
     "    if (receive_by_copy) {\n"
     "        // InitializeIrNop: the game takes the payload itself with ReceiveIrnop.\n"
     "        received_packets.emplace_back(payload.begin(), payload.end());\n"
     "        receive_event->Signal();\n"
     "        return;\n"
     "    }\n"),
    ("    std::memcpy(shared_memory->GetPointer(), &shared_memory_init, sizeof(SharedMemoryHeader));\n",
     "    std::memcpy(shared_memory->GetPointer(), &shared_memory_init, sizeof(SharedMemoryHeader));\n"
     "    receive_by_copy = false;\n"
     "    received_packets.clear();\n"),
    ("    shared_memory = nullptr;\n    receive_buffer = nullptr;\n",
     "    shared_memory = nullptr;\n    receive_buffer = nullptr;\n"
     "    receive_by_copy = false;\n    received_packets.clear();\n"),
    ("void IR_USER::GetConnectionStatus(Kernel::HLERequestContext& ctx) {\n", NEW_FUNCTIONS),
    ("        {0x0001, nullptr, \"InitializeIrNop\"},\n",
     "        {0x0001, &IR_USER::InitializeIrNop, \"InitializeIrNop\"},\n"),
    ("        {0x000E, nullptr, \"SendIrNopLarge\"},\n",
     "        {0x000E, &IR_USER::SendIrNopLarge, \"SendIrNopLarge\"},\n"),
    ("        {0x000F, nullptr, \"ReceiveIrnop\"},\n",
     "        {0x000F, &IR_USER::ReceiveIrnop, \"ReceiveIrnop\"},\n"),
    ("        {0x0010, nullptr, \"ReceiveIrnopLarge\"},\n",
     "        {0x0010, &IR_USER::ReceiveIrnopLarge, \"ReceiveIrnopLarge\"},\n"),
]


def plan(path, edits):
    raw = path.read_bytes()
    crlf = b"\r\n" in raw
    text = raw.decode("utf-8").replace("\r\n", "\n")
    for old, new in edits:
        if new in text:
            continue
        assert text.count(old) == 1, f"{path.name}: anchor found {text.count(old)} times: {old[:70]!r}"
        text = text.replace(old, new)
    return text, crlf


def main():
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    ir = pathlib.Path(sys.argv[1]) / "src" / "core" / "hle" / "service" / "ir"
    if "AutoConnection" not in (ir / "ir_user.cpp").read_text(encoding="utf-8"):
        print("apply_portal_patch.py first")
        return 1
    work = [(path, *plan(path, edits)) for path, edits in ((ir / "ir_user.h", H_EDITS), (ir / "ir_user.cpp", CPP_EDITS))]
    for path, text, crlf in work:
        with open(path, "w", encoding="utf-8", newline="\r\n" if crlf else "\n") as f:
            f.write(text)
        print(f"{path.name}: patched")
    return 0


if __name__ == "__main__":
    sys.exit(main())
