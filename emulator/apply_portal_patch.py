"""apply_portal_patch.py <azahar checkout>: steps 2 and 3 of docs/plan.md in an Azahar source tree (tag 2126.2).

ir:USER's AutoConnection (0x0007), which the Skylanders 3DS games call at "Aim at the PORTAL OF POWER", connects a
new infrared device, SkylandersPortal, the way RequireConnection connects the Circle Pad Pro; SendIrNop then goes to
the connected device instead of always to the Circle Pad Pro. Every packet the game sends is ff ff ff and a console
portal command; the device answers them as skylanders-portal's SoftwarePortal answers a console game (R, A, S with a
counter, Q, W), with one figure on slot 0 from the file SKYLANDERS_PORTAL_FIGURE names (never written back);
SKYLANDERS_PORTAL_SCRIPT lifts and places toys at given seconds in scripted runs. For
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
#include <chrono>
#include <mutex>
#include <span>
#include <string>
#include <utility>
#include <vector>
#include "core/hle/service/ir/ir_user.h"

namespace Service::IR {

/// The figure on the Skylanders portal (slot 0), shared by the frontend (Skylanders > Place
/// figure...) and the portal device. The file is read once and never written: what the game
/// writes stays in memory.
class SkylandersPortalFigure {
public:
    static SkylandersPortalFigure& Instance();

    /// Reads a 1024-byte figure file and puts it on the portal; the one there before is lifted.
    bool Place(const std::string& path);
    void Remove();
    /// The file on the portal, empty without one.
    std::string Path() const;
    bool Present() const;
    /// Changes with every Place / Remove, so the device can tell the game.
    u32 Generation() const;
    std::array<u8, 1024> Data() const;
    void WriteBlock(u8 block, std::span<const u8> bytes);

private:
    mutable std::mutex mutex;
    std::string path;
    std::array<u8, 1024> data{};
    bool present = false;
    u32 generation = 0;
};

/// The Skylanders 3DS Portal of Power, which talks to the game over infrared once AutoConnection
/// connected it. Every packet from the game is the portal light's colour (r g b) and then a
/// console portal command (R, A, C, S, Q, W); the device answers like skylanders-portal's
/// SoftwarePortal, with the figure SkylandersPortalFigure holds on slot 0. For scripted runs
/// SKYLANDERS_PORTAL_FIGURE names figure files (paths separated by ';'): the first goes on at the
/// first connection, and after the game has read one and reconnects, the next.
/// SKYLANDERS_PORTAL_SCRIPT times toys for scripted runs: "<seconds>:lift" or "<seconds>:place
/// <file>", separated by ';', in seconds since the device was made (the emulated system's start),
/// each done with the first packet or connection after its time (SuperChargers Racing waits with
/// "Wrong toy!" until a vehicle is lifted off its driver tab). To try other answers,
/// SKYLANDERS_PORTAL_REPLIES names a table of hex replies that comes first. Everything is logged
/// (Service.IR, Info), to learn the protocol.
class SkylandersPortal final : public IRDevice {
public:
    explicit SkylandersPortal(SendFunc send_func);
    ~SkylandersPortal() override;

    void OnConnect() override;
    void OnDisconnect() override;
    void OnReceive(std::span<const u8> data) override;

private:
    bool ReplyFromTable(std::span<const u8> data);
    void RunScript();
    void Answer(std::span<const u8> command);
    void Reply(const std::vector<u8>& reply);
    bool Logged() const;
    u8 SlotState();

    u32 received_packets = 0;
    bool active = false;
    u8 counter = 0;
    bool list_loaded = false;
    std::vector<std::string> list;  // SKYLANDERS_PORTAL_FIGURE, in order
    size_t current = 0;             // the list's figure on the portal
    int reads = 0;                  // blocks the game has read since the figure went on
    u32 seen_generation = 0;        // SkylandersPortalFigure's, as last reported
    bool lifting = false;           // the next status says the old figure is being lifted
    u8 state = 0;                   // slot 0's status bits: 0 empty, 1 on, 2 lifted, 3 just put on
    int added_reports = 0;          // status reports still to say "just put on"
    bool script_loaded = false;
    std::vector<std::pair<double, std::string>> script;  // SKYLANDERS_PORTAL_SCRIPT: (seconds, action)
    size_t script_next = 0;                              // the first action not done yet
    std::chrono::steady_clock::time_point made = std::chrono::steady_clock::now();
};

} // namespace Service::IR
"""

PORTAL_CPP = """// Copyright 2026 tsapZ
// Licensed under GPLv2 or any later version (part of Azahar)
// Refer to the license.txt file included.

#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <filesystem>
#include <fstream>
#include <iterator>
#include <stdexcept>
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

SkylandersPortalFigure& SkylandersPortalFigure::Instance() {
    static SkylandersPortalFigure figure;
    return figure;
}

bool SkylandersPortalFigure::Place(const std::string& file) {
    // A UTF-8 path (the frontend's file dialog; the scripted list is plain ASCII).
    std::ifstream in(std::filesystem::path(std::u8string(file.begin(), file.end())), std::ios::binary);
    const std::vector<char> bytes{std::istreambuf_iterator<char>(in), std::istreambuf_iterator<char>()};
    if (bytes.size() != 1024) {
        LOG_WARNING(Service_IR, "Skylanders portal: {} is not a 1024-byte figure file", file);
        return false;
    }
    std::scoped_lock lock{mutex};
    std::copy(bytes.begin(), bytes.end(), data.begin());
    path = file;
    present = true;
    ++generation;
    LOG_INFO(Service_IR, "Skylanders portal: figure on the portal: {}", file);
    return true;
}

void SkylandersPortalFigure::Remove() {
    std::scoped_lock lock{mutex};
    present = false;
    path.clear();
    ++generation;
    LOG_INFO(Service_IR, "Skylanders portal: figure lifted off");
}

std::string SkylandersPortalFigure::Path() const {
    std::scoped_lock lock{mutex};
    return path;
}

bool SkylandersPortalFigure::Present() const {
    std::scoped_lock lock{mutex};
    return present;
}

u32 SkylandersPortalFigure::Generation() const {
    std::scoped_lock lock{mutex};
    return generation;
}

std::array<u8, 1024> SkylandersPortalFigure::Data() const {
    std::scoped_lock lock{mutex};
    return data;
}

void SkylandersPortalFigure::WriteBlock(u8 block, std::span<const u8> bytes) {
    std::scoped_lock lock{mutex};
    if (present && block < 64 && bytes.size() >= 16) {
        std::copy_n(bytes.begin(), 16, data.begin() + block * 16);
    }
}

SkylandersPortal::SkylandersPortal(SendFunc send_func) : IRDevice(std::move(send_func)) {}

SkylandersPortal::~SkylandersPortal() = default;

void SkylandersPortal::RunScript() {
    if (!script_loaded) {
        script_loaded = true;
        const char* env = std::getenv("SKYLANDERS_PORTAL_SCRIPT");
        const std::string text = env ? env : "";
        size_t start = 0;
        while (start < text.size()) {
            size_t end = text.find(';', start);
            if (end == std::string::npos) {
                end = text.size();
            }
            const std::string item = text.substr(start, end - start);
            const size_t colon = item.find(':');
            if (colon != std::string::npos && colon > 0) {
                try {
                    std::string action = item.substr(colon + 1);
                    action.erase(0, action.find_first_not_of(' '));
                    script.emplace_back(std::stod(item.substr(0, colon)), action);
                } catch (const std::exception&) {
                    LOG_WARNING(Service_IR, "Skylanders portal: script item '{}' has no time", item);
                }
            }
            start = end + 1;
        }
        std::stable_sort(script.begin(), script.end(),
                         [](const auto& a, const auto& b) { return a.first < b.first; });
    }
    const double now = std::chrono::duration<double>(std::chrono::steady_clock::now() - made).count();
    SkylandersPortalFigure& figure = SkylandersPortalFigure::Instance();
    while (script_next < script.size() && script[script_next].first <= now) {
        const std::string& action = script[script_next].second;
        LOG_INFO(Service_IR, "Skylanders portal: script at {:.1f} s: {}", now, action);
        if (action == "lift") {
            figure.Remove();
        } else if (action.rfind("place ", 0) == 0) {
            figure.Place(action.substr(6));
        } else {
            LOG_WARNING(Service_IR, "Skylanders portal: unknown script action '{}'", action);
        }
        ++script_next;
    }
}

void SkylandersPortal::OnConnect() {
    received_packets = 0;
    RunScript();
    SkylandersPortalFigure& figure = SkylandersPortalFigure::Instance();
    if (!list_loaded) {
        list_loaded = true;
        const char* paths = std::getenv("SKYLANDERS_PORTAL_FIGURE");
        const std::string text = paths ? paths : "";
        size_t start = 0;
        while (start < text.size()) {
            size_t end = text.find(';', start);
            if (end == std::string::npos) {
                end = text.size();
            }
            if (end > start) {
                list.push_back(text.substr(start, end - start));
            }
            start = end + 1;
        }
        if (!list.empty() && !figure.Present()) {
            figure.Place(list[0]);
        }
    } else if (reads > 0 && current + 1 < list.size()) {
        // The game reconnects after it has read a figure: now the list's next one stands there.
        ++current;
        figure.Place(list[current]);
    }
    // Each connection starts over: the game activates the portal again, which announces the
    // figure as just put on.
    reads = 0;
    seen_generation = figure.Generation();
    active = false;
    lifting = false;
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
    RunScript();
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

// Slot 0's status bits for this report. A figure placed or lifted in the frontend meanwhile: the
// one there before is reported as lifted once, then the new one as just put on (as a real portal
// and skylanders-portal's SoftwarePortal do).
u8 SkylandersPortal::SlotState() {
    const SkylandersPortalFigure& figure = SkylandersPortalFigure::Instance();
    const u32 generation = figure.Generation();
    if (generation != seen_generation) {
        seen_generation = generation;
        reads = 0;
        if (active) {
            lifting = state != 0;
            state = figure.Present() ? 3 : 0;
            added_reports = kAddedReports;
        }
    }
    if (!active) {
        return 0;
    }
    if (lifting) {
        lifting = false;
        return 2;
    }
    const u8 now = state;
    if (state == 3 && --added_reports <= 0) {
        state = 1;
    }
    return now;
}

// As skylanders-portal's SoftwarePortal answers a console game, the figure on slot 0.
void SkylandersPortal::Answer(std::span<const u8> command) {
    if (command.empty()) {
        return;
    }
    SkylandersPortalFigure& figure = SkylandersPortalFigure::Instance();
    switch (command[0]) {
    case 'R': // ready: a Trap Team portal, as the USB ones answer
        Reply({0x52, 0x02, 0x1b});
        break;
    case 'A': { // activate (argument != 0) or deactivate
        const u8 argument = command.size() > 1 ? command[1] : 0;
        const bool activate = argument != 0;
        if (activate && !active && figure.Present()) {
            state = 3; // reported as just put on when the portal turns on
            added_reports = kAddedReports;
        } else if (!activate) {
            state = 0; // the figure stays, it just isn't reported
        }
        active = activate;
        seen_generation = figure.Generation();
        lifting = false;
        Reply({0x41, argument, 0xff, 0x77});
        break;
    }
    case 'S': { // status: two bits a slot, a counter, whether the portal is on
        const u8 slot0 = SlotState();
        Reply({0x53, slot0, 0, 0, 0, counter++, static_cast<u8>(active ? 1 : 0)});
        break;
    }
    case 'Q': { // read a block: 51, 0x10 | slot when there is a figure, the block, 16 bytes
        const u8 slot = command.size() > 1 ? static_cast<u8>(command[1] & 0x0f) : 0;
        const u8 block = command.size() > 2 ? command[2] : 0;
        std::vector<u8> out{0x51, slot, block};
        out.resize(3 + 16);
        if (slot == 0 && figure.Present() && block < 64) {
            const std::array<u8, 1024> data = figure.Data();
            out[1] |= 0x10;
            std::copy_n(data.begin() + block * 16, 16, out.begin() + 3);
            ++reads;
        }
        Reply(out);
        break;
    }
    case 'W': { // write a block: kept in memory only, the file is never written
        const u8 slot = command.size() > 1 ? static_cast<u8>(command[1] & 0x0f) : 0;
        const u8 block = command.size() > 2 ? command[2] : 0;
        std::vector<u8> out{0x57, slot, block};
        if (slot == 0 && figure.Present() && block < 64 && command.size() >= 3 + 16) {
            out[1] |= 0x10;
            figure.WriteBlock(block, command.subspan(3, 16));
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

# The frontend: File > Skylanders Portal > Place figure... / Lift figure off, next to Amiibo, while a game runs.
QT_UI_EDITS = [
    (r"""    <widget class="QMenu" name="menu_Open_Folder">
""",
     r"""    <widget class="QMenu" name="menu_Skylanders">
     <property name="title">
      <string>Skylanders Portal</string>
     </property>
     <addaction name="action_Place_Skylander"/>
     <addaction name="action_Lift_Skylander"/>
    </widget>
    <widget class="QMenu" name="menu_Open_Folder">
"""),
    (r"""    <addaction name="menu_Amiibo"/>
""",
     r"""    <addaction name="menu_Amiibo"/>
    <addaction name="menu_Skylanders"/>
"""),
    (r"""  <action name="action_Open_Citra_Folder">
""",
     r"""  <action name="action_Place_Skylander">
   <property name="enabled">
    <bool>false</bool>
   </property>
   <property name="text">
    <string>Place figure...</string>
   </property>
  </action>
  <action name="action_Lift_Skylander">
   <property name="enabled">
    <bool>false</bool>
   </property>
   <property name="text">
    <string>Lift figure off</string>
   </property>
  </action>
  <action name="action_Open_Citra_Folder">
"""),
]

QT_H_EDITS = [
    ("    void OnRemoveAmiibo();\n",
     "    void OnRemoveAmiibo();\n    void OnPlaceSkylander();\n    void OnLiftSkylander();\n"),
]

QT_CPP_EDITS = [
    ('#include "core/hle/service/nfc/nfc.h"\n',
     '#include "core/hle/service/ir/skylanders_portal.h"\n#include "core/hle/service/nfc/nfc.h"\n'),
    ("    connect_menu(ui->action_Remove_Amiibo, &GMainWindow::OnRemoveAmiibo);\n",
     "    connect_menu(ui->action_Remove_Amiibo, &GMainWindow::OnRemoveAmiibo);\n"
     "    connect_menu(ui->action_Place_Skylander, &GMainWindow::OnPlaceSkylander);\n"
     "    connect_menu(ui->action_Lift_Skylander, &GMainWindow::OnLiftSkylander);\n"),
    ("        ui->action_Remove_Amiibo,\n",
     "        ui->action_Remove_Amiibo,\n        ui->action_Place_Skylander,\n        ui->action_Lift_Skylander,\n"),
    (r"""void GMainWindow::OnOpenCitraFolder() {
""",
     r"""// The Skylanders 3DS portal (core/hle/service/ir/skylanders_portal.h): a figure file onto it, the
// one there before lifted off. The same 1024-byte files the Xbox 360 ports keep in
// Documents\Skylanders\Figures; the file itself is never written.
void GMainWindow::OnPlaceSkylander() {
    const QString start = QDir(QStandardPaths::writableLocation(QStandardPaths::DocumentsLocation))
                              .filePath(QStringLiteral("Skylanders/Figures"));
    const QString filter = tr("Skylanders figure") + QStringLiteral(" (*.dump *.bin *.sky);;") +
                           tr("All Files") + QStringLiteral(" (*.*)");
    const QString filename =
        QFileDialog::getOpenFileName(this, tr("Place a figure on the portal"), start, filter);
    if (filename.isEmpty()) {
        return;
    }
    if (!Service::IR::SkylandersPortalFigure::Instance().Place(filename.toStdString())) {
        QMessageBox::warning(this, tr("Skylanders Portal"),
                             tr("\"%1\" isn't a figure file (1024 bytes).").arg(filename));
    }
}

void GMainWindow::OnLiftSkylander() {
    Service::IR::SkylandersPortalFigure::Instance().Remove();
}

void GMainWindow::OnOpenCitraFolder() {
"""),
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
                        (root / "src" / "core" / "CMakeLists.txt", CMAKE_EDITS),
                        (root / "src" / "citra_qt" / "main.ui", QT_UI_EDITS),
                        (root / "src" / "citra_qt" / "citra_qt.h", QT_H_EDITS),
                        (root / "src" / "citra_qt" / "citra_qt.cpp", QT_CPP_EDITS)):
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
