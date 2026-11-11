"""apply_portal_patch.py <azahar checkout>: steps 2 and 3 of docs/plan.md in an Azahar source tree (tag 2126.2).

ir:USER's AutoConnection (0x0007), which the Skylanders 3DS games call at "Aim at the PORTAL OF POWER", connects a
new infrared device, SkylandersPortal, the way RequireConnection connects the Circle Pad Pro; SendIrNop then goes to
the connected device instead of always to the Circle Pad Pro. Every packet the game sends is ff ff ff and a console
portal command; the device answers them as skylanders-portal's SoftwarePortal answers a console game (R, A, S with a
counter, Q, W), with one figure on slot 0 from the file SKYLANDERS_PORTAL_FIGURE names (never written back). For
experiments a table of hex replies named by SKYLANDERS_PORTAL_REPLIES comes first. Everything is logged (Service.IR,
Info). GetConnectionStatus (0x0013) and GetConnectionRole (0x0017) answer from the shared memory header. All edits
are checked before anything is written; a second run changes nothing.
The new files are under Azahar's license (GPLv2 or later), as part of it. Stdlib only."""
import pathlib
import sys

PORTAL_H = """// Copyright 2026 tsapZ
// Licensed under GPLv2 or any later version (part of Azahar)
// Refer to the license.txt file included.

#pragma once

#include <array>
#include <span>
#include <vector>
#include "core/hle/service/ir/ir_user.h"

namespace Service::IR {

/// The Skylanders 3DS Portal of Power, which talks to the game over infrared once AutoConnection
/// connected it. Every packet from the game is the portal light's colour (r g b) and then a
/// console portal command (R, A, C, S, Q, W); the device answers like skylanders-portal's
/// SoftwarePortal, with a figure on slot 0 from the files SKYLANDERS_PORTAL_FIGURE names (paths
/// separated by ';', read once, never written: what the game writes stays in memory). The game
/// reconnects after reading a figure; then the next one in the list stands on the portal, as if
/// the player had swapped them. To try other answers, SKYLANDERS_PORTAL_REPLIES names a table of
/// hex replies that comes first. Everything is logged (Service.IR, Info), to learn the protocol.
class SkylandersPortal final : public IRDevice {
public:
    explicit SkylandersPortal(SendFunc send_func);
    ~SkylandersPortal() override;

    void OnConnect() override;
    void OnDisconnect() override;
    void OnReceive(std::span<const u8> data) override;

private:
    bool ReplyFromTable(std::span<const u8> data);
    void Answer(std::span<const u8> command);
    void Reply(const std::vector<u8>& reply);
    bool Logged() const;

    u32 received_packets = 0;
    bool active = false;
    u8 counter = 0;
    bool figures_loaded = false;
    std::vector<std::array<u8, 1024>> figures;  // SKYLANDERS_PORTAL_FIGURE, in order
    size_t current = 0;                         // the one on slot 0
    int reads = 0;                              // its blocks the game has read
    bool present = false;   // a figure on slot 0
    u8 state = 0;           // its status bits: 0 empty, 1 on, 3 just put on
    int added_reports = 0;  // status reports still to say "just put on"
};

} // namespace Service::IR
"""

PORTAL_CPP = """// Copyright 2026 tsapZ
// Licensed under GPLv2 or any later version (part of Azahar)
// Refer to the license.txt file included.

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <fstream>
#include <iterator>
#include <string>
#include <utility>
#include <vector>
#include <fmt/ranges.h>
#include "common/logging/log.h"
#include "core/hle/service/ir/skylanders_portal.h"

namespace Service::IR {

namespace {

// "ff ff ff 52 00" -> its bytes; stops at the first token that isn't a hex byte.
std::vector<u8> ParseHex(const std::string& text) {
    std::vector<u8> bytes;
    size_t at = 0;
    while (at < text.size()) {
        while (at < text.size() && std::isspace(static_cast<unsigned char>(text[at]))) {
            ++at;
        }
        if (at + 1 >= text.size() || !std::isxdigit(static_cast<unsigned char>(text[at])) ||
            !std::isxdigit(static_cast<unsigned char>(text[at + 1]))) {
            break;
        }
        bytes.push_back(static_cast<u8>(std::stoul(text.substr(at, 2), nullptr, 16)));
        at += 2;
    }
    return bytes;
}

// Status reports that say "just put on" before "on" (skylanders-portal's kAddedReports).
constexpr int kAddedReports = 8;

} // namespace

SkylandersPortal::SkylandersPortal(SendFunc send_func) : IRDevice(std::move(send_func)) {}

SkylandersPortal::~SkylandersPortal() = default;

void SkylandersPortal::OnConnect() {
    received_packets = 0;
    if (!figures_loaded) {
        figures_loaded = true;
        const char* list = std::getenv("SKYLANDERS_PORTAL_FIGURE");
        std::string paths = list ? list : "";
        size_t start = 0;
        while (start < paths.size()) {
            size_t end = paths.find(';', start);
            if (end == std::string::npos) {
                end = paths.size();
            }
            const std::string path = paths.substr(start, end - start);
            start = end + 1;
            if (path.empty()) {
                continue;
            }
            std::ifstream in(path, std::ios::binary);
            const std::vector<char> bytes{std::istreambuf_iterator<char>(in),
                                          std::istreambuf_iterator<char>()};
            const bool ok = bytes.size() == 1024;
            if (ok) {
                std::array<u8, 1024>& figure = figures.emplace_back();
                std::copy(bytes.begin(), bytes.end(), figure.begin());
            }
            LOG_INFO(Service_IR, "Skylanders portal: figure file {}: {}", path,
                     ok ? "figure " + std::to_string(figures.size())
                        : std::string("not a 1024-byte figure, left out"));
        }
    } else if (reads > 0 && current + 1 < figures.size()) {
        // The game reconnects after it has read a figure: now the next one stands on the portal.
        ++current;
        reads = 0;
        LOG_INFO(Service_IR, "Skylanders portal: figure {} of {} on slot 0 now", current + 1,
                 figures.size());
    }
    present = current < figures.size();
    // Each connection starts over: the game activates the portal again, which announces the
    // figure as just put on.
    active = false;
    state = 0;
    LOG_INFO(Service_IR, "Skylanders portal: connected");
}

void SkylandersPortal::OnDisconnect() {
    LOG_INFO(Service_IR, "Skylanders portal: disconnected after {} packets from the game",
             received_packets);
}

bool SkylandersPortal::Logged() const {
    // Every packet for the first 200, then every 50th: the protocol without a huge log.
    return received_packets <= 200 || received_packets % 50 == 0;
}

void SkylandersPortal::Reply(const std::vector<u8>& reply) {
    if (Logged()) {
        LOG_INFO(Service_IR, "Skylanders portal: replying {} bytes: {:02x}", reply.size(),
                 fmt::join(reply, " "));
    }
    Send(reply);
}

void SkylandersPortal::OnReceive(std::span<const u8> data) {
    ++received_packets;
    if (Logged()) {
        LOG_INFO(Service_IR, "Skylanders portal: the game sent {} bytes (packet {}): {:02x}",
                 data.size(), received_packets, fmt::join(data, " "));
    }
    if (ReplyFromTable(data)) {
        return;
    }
    // Every packet starts with the portal light's colour (r g b: ff ff ff at first, then what the
    // last C set, e.g. 00 00 5b), then the command.
    if (data.size() > 3) {
        Answer(data.subspan(3));
    }
}

// SKYLANDERS_PORTAL_REPLIES names a text file of "<request> => <reply>" lines in hex ('#' starts a
// comment). The first line whose request starts this packet gives the reply (an empty one: none);
// read again for every packet, so it can change while the game runs.
bool SkylandersPortal::ReplyFromTable(std::span<const u8> data) {
    const char* path = std::getenv("SKYLANDERS_PORTAL_REPLIES");
    if (!path) {
        return false;
    }
    std::ifstream in(path);
    std::string line;
    while (std::getline(in, line)) {
        if (line.empty() || line[0] == '#') {
            continue;
        }
        const size_t arrow = line.find("=>");
        if (arrow == std::string::npos) {
            continue;
        }
        const std::vector<u8> request = ParseHex(line.substr(0, arrow));
        if (request.empty() || request.size() > data.size() ||
            !std::equal(request.begin(), request.end(), data.begin())) {
            continue;
        }
        const std::vector<u8> reply = ParseHex(line.substr(arrow + 2));
        if (!reply.empty()) {
            Reply(reply);
        }
        return true;
    }
    return false;
}

// As skylanders-portal's SoftwarePortal answers a console game, one figure on slot 0.
void SkylandersPortal::Answer(std::span<const u8> command) {
    if (command.empty()) {
        return;
    }
    switch (command[0]) {
    case 'R': // ready: a Trap Team portal, as the USB ones answer
        Reply({0x52, 0x02, 0x1b});
        break;
    case 'A': { // activate (argument != 0) or deactivate
        const u8 argument = command.size() > 1 ? command[1] : 0;
        const bool activate = argument != 0;
        if (activate && !active && present) {
            state = 3; // reported as just put on when the portal turns on
            added_reports = kAddedReports;
        } else if (!activate) {
            state = 0; // the figure stays, it just isn't reported
        }
        active = activate;
        Reply({0x41, argument, 0xff, 0x77});
        break;
    }
    case 'S': { // status: two bits a slot, a counter, whether the portal is on
        const u8 slot0 = active ? state : 0;
        Reply({0x53, slot0, 0, 0, 0, counter++, static_cast<u8>(active ? 1 : 0)});
        if (state == 3 && --added_reports <= 0) {
            state = 1;
        }
        break;
    }
    case 'Q': { // read a block: 51, 0x10 | slot when there is a figure, the block, 16 bytes
        const u8 slot = command.size() > 1 ? static_cast<u8>(command[1] & 0x0f) : 0;
        const u8 block = command.size() > 2 ? command[2] : 0;
        std::vector<u8> out{0x51, slot, block};
        out.resize(3 + 16);
        if (slot == 0 && present && block < 64) {
            out[1] |= 0x10;
            std::copy_n(figures[current].begin() + block * 16, 16, out.begin() + 3);
            ++reads;
        }
        Reply(out);
        break;
    }
    case 'W': { // write a block: kept in memory only, the file is never written
        const u8 slot = command.size() > 1 ? static_cast<u8>(command[1] & 0x0f) : 0;
        const u8 block = command.size() > 2 ? command[2] : 0;
        std::vector<u8> out{0x57, slot, block};
        if (slot == 0 && present && block < 64 && command.size() >= 3 + 16) {
            out[1] |= 0x10;
            std::copy_n(command.begin() + 3, 16, figures[current].begin() + block * 16);
            LOG_INFO(Service_IR, "Skylanders portal: the game wrote block {}", block);
        }
        Reply(out);
        break;
    }
    default: // C (the light) and the rest: no answer
        break;
    }
}

} // namespace Service::IR
"""

H_EDITS = [
    ("class BufferManager;\nclass ExtraHID;\n",
     "class BufferManager;\nclass ExtraHID;\nclass SkylandersPortal;\n"),
    ("    void RequireConnection(Kernel::HLERequestContext& ctx);\n",
     "    void RequireConnection(Kernel::HLERequestContext& ctx);\n"
     "\n"
     "    /**\n"
     "     * AutoConnection service function (Skylanders 3DS: at \"Aim at the PORTAL OF POWER\")\n"
     "     * Connects the Skylanders portal device. Inputs (as the game sends them): 1 : 0xff, then\n"
     "     * five 64-bit values of unknown meaning (3000000, 3694000, 11083024, 13302000, 13302000).\n"
     "     *  Outputs:\n"
     "     *      1 : Result of function, 0 on success, otherwise error code\n"
     "     */\n"
     "    void AutoConnection(Kernel::HLERequestContext& ctx);\n"
     "\n"
     "    /// GetConnectionStatus service function: 1 : result, 2 : connection status (u8)\n"
     "    void GetConnectionStatus(Kernel::HLERequestContext& ctx);\n"
     "\n"
     "    /// GetConnectionRole service function: 1 : result, 2 : connection role (u8)\n"
     "    void GetConnectionRole(Kernel::HLERequestContext& ctx);\n"
     "\n"
     "    /// The connected device (the Circle Pad Pro unless AutoConnection connected the portal).\n"
     "    IRDevice* ActiveDevice();\n"),
    ("    std::unique_ptr<ExtraHID> extra_hid;\n",
     "    std::unique_ptr<ExtraHID> extra_hid;\n"
     "    std::unique_ptr<SkylandersPortal> skylanders_portal;\n"
     "    // Not serialized: after a state load the Circle Pad Pro is the device again.\n"
     "    IRDevice* active_device = nullptr;\n"),
]

CPP_NEW_FUNCTIONS = """IRDevice* IR_USER::ActiveDevice() {
    return active_device ? active_device : static_cast<IRDevice*>(extra_hid.get());
}

void IR_USER::AutoConnection(Kernel::HLERequestContext& ctx) {
    IPC::RequestParser rp(ctx);
    const u32 first = rp.Pop<u32>();
    std::array<u64, 5> values{};
    for (auto& value : values) {
        value = rp.Pop<u64>();
    }

    IPC::RequestBuilder rb = rp.MakeBuilder(1, 0);
    if (!shared_memory) {
        LOG_ERROR(Service_IR, "AutoConnection before InitializeIrNopShared");
        rb.Push(ResultSuccess);
        return;
    }
    u8* shared_memory_ptr = shared_memory->GetPointer();
    // As RequireConnection sets them for the Circle Pad Pro (values seen on a New 3DS there).
    shared_memory_ptr[offsetof(SharedMemoryHeader, connection_status)] = 2;
    shared_memory_ptr[offsetof(SharedMemoryHeader, connection_role)] = 2;
    shared_memory_ptr[offsetof(SharedMemoryHeader, connected)] = 1;

    connected_device = true;
    active_device = skylanders_portal.get();
    skylanders_portal->OnConnect();
    conn_status_event->Signal();
    rb.Push(ResultSuccess);

    LOG_INFO(Service_IR, "called, 0x{:x}, {}, {}, {}, {}, {}: Skylanders portal connected", first,
             values[0], values[1], values[2], values[3], values[4]);
}

void IR_USER::GetConnectionStatus(Kernel::HLERequestContext& ctx) {
    IPC::RequestParser rp(ctx);
    IPC::RequestBuilder rb = rp.MakeBuilder(2, 0);
    rb.Push(ResultSuccess);
    rb.Push(static_cast<u32>(
        shared_memory ? shared_memory->GetPointer()[offsetof(SharedMemoryHeader, connection_status)]
                      : 0));
    LOG_DEBUG(Service_IR, "called");
}

void IR_USER::GetConnectionRole(Kernel::HLERequestContext& ctx) {
    IPC::RequestParser rp(ctx);
    IPC::RequestBuilder rb = rp.MakeBuilder(2, 0);
    rb.Push(ResultSuccess);
    rb.Push(static_cast<u32>(
        shared_memory ? shared_memory->GetPointer()[offsetof(SharedMemoryHeader, connection_role)]
                      : 0));
    LOG_DEBUG(Service_IR, "called");
}

IR_USER::IR_USER(Core::System& system) : ServiceFramework("ir:USER", 1) {
"""

CPP_EDITS = [
    ('#include "core/hle/service/ir/ir_user.h"\n',
     '#include "core/hle/service/ir/ir_user.h"\n#include "core/hle/service/ir/skylanders_portal.h"\n'),
    ("        connected_device = true;\n        extra_hid->OnConnect();\n",
     "        connected_device = true;\n        active_device = extra_hid.get();\n        extra_hid->OnConnect();\n"),
    # Disconnect
    ("    if (connected_device) {\n        extra_hid->OnDisconnect();\n        connected_device = false;\n        conn_status_event->Signal();\n    }\n",
     "    if (connected_device) {\n        ActiveDevice()->OnDisconnect();\n        connected_device = false;\n        active_device = nullptr;\n        conn_status_event->Signal();\n    }\n"),
    # FinalizeIrNop
    ("    if (connected_device) {\n        extra_hid->OnDisconnect();\n        connected_device = false;\n    }\n",
     "    if (connected_device) {\n        ActiveDevice()->OnDisconnect();\n        connected_device = false;\n        active_device = nullptr;\n    }\n"),
    ("        extra_hid->OnReceive(buffer);\n", "        ActiveDevice()->OnReceive(buffer);\n"),
    ("        {0x0007, nullptr, \"AutoConnection\"},\n", "        {0x0007, &IR_USER::AutoConnection, \"AutoConnection\"},\n"),
    ("        {0x0013, nullptr, \"GetConnectionStatus\"},\n", "        {0x0013, &IR_USER::GetConnectionStatus, \"GetConnectionStatus\"},\n"),
    ("        {0x0017, nullptr, \"GetConnectionRole\"},\n", "        {0x0017, &IR_USER::GetConnectionRole, \"GetConnectionRole\"},\n"),
    ("IR_USER::IR_USER(Core::System& system) : ServiceFramework(\"ir:USER\", 1) {\n", CPP_NEW_FUNCTIONS),
    ("                                           system.CoreTiming(), system.Movie());\n}\n",
     "                                           system.CoreTiming(), system.Movie());\n"
     "    skylanders_portal = std::make_unique<SkylandersPortal>(\n"
     "        [this](std::span<const u8> data) { PutToReceive(data); });\n}\n"),
    # Destructor
    ("IR_USER::~IR_USER() {\n    if (connected_device) {\n        extra_hid->OnDisconnect();\n    }\n}\n",
     "IR_USER::~IR_USER() {\n    if (connected_device) {\n        ActiveDevice()->OnDisconnect();\n    }\n}\n"),
]

CMAKE_EDITS = [
    ("    hle/service/ir/ir_user.h\n",
     "    hle/service/ir/ir_user.h\n    hle/service/ir/skylanders_portal.cpp\n    hle/service/ir/skylanders_portal.h\n"),
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
    root = pathlib.Path(sys.argv[1])
    ir = root / "src" / "core" / "hle" / "service" / "ir"
    work = []
    for path, edits in ((ir / "ir_user.h", H_EDITS), (ir / "ir_user.cpp", CPP_EDITS),
                        (root / "src" / "core" / "CMakeLists.txt", CMAKE_EDITS)):
        text, crlf = plan(path, edits)
        work.append((path, text, crlf))
    for path, text, crlf in work:
        with open(path, "w", encoding="utf-8", newline="\r\n" if crlf else "\n") as f:
            f.write(text)
        print(f"{path.name}: patched")
    for name, text in (("skylanders_portal.h", PORTAL_H), ("skylanders_portal.cpp", PORTAL_CPP)):
        with open(ir / name, "w", encoding="utf-8", newline="\n") as f:
            f.write(text)
        print(f"{name}: written")
    return 0


if __name__ == "__main__":
    sys.exit(main())
