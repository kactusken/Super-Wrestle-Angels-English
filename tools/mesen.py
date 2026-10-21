#!/usr/bin/env python3
"""Drive the game headless in Mesen 2 (--testrunner) from a list of steps: input, screenshots,
savestates, memory dumps and access traces. For research and automated checks, not releases.

  mesen.py [--rom ROM] [--out DIR] [--max-frames N] STEP...
  mesen.py --file STEPS.txt

Steps (one per argument, or one per line in --file; # starts a comment):
  wait N                    run N frames
  press BUTTONS [N]         hold buttons (a+b, start, up ...) for N frames (default 3), then 3 free
  mash BUTTONS FRAMES [EVERY]  press repeatedly for FRAMES frames, every EVERY frames (default 12)
  shot NAME                 screenshot -> OUT/NAME.png
  save NAME / load NAME     savestate -> / <- OUT/states/NAME.mss
  dump MEM START LEN NAME   memory -> OUT/NAME.bin (MEM: wram, vram, cgram, oam, rom, sram, bus)
  poke ADDR BYTE            write a byte to the CPU bus (WRAM: $7E0000-$7FFFFF)
  write MEM START FILE      write a file's bytes into memory (e.g. new tiles into a state's VRAM)
  trace KIND START END [MAX] log accesses (read|write|exec) on the CPU bus in START..END with PC,
                            A/X/Y and the value, up to MAX lines (default 2000) -> OUT/trace.txt.
                            I/O registers only match at the address used: $80:2118 is not $00:2118.
                            DMA transfers don't show as CPU reads.
  untrace                   stop all traces
  regs PREFIX NAME          Mesen state values starting with PREFIX (ppu., cpu.) -> OUT/NAME.txt
  cdl NAME                  Mesen's code/data log of the ROM -> OUT/NAME.cdl (one flag byte per
                            ROM byte: 1 = executed as code, 2 = read as data)
  until ADDR BYTE [LIMIT]   run until bus byte ADDR == BYTE (at most LIMIT frames, default 600)

Buttons: a b x y l r start select up down left right. Addresses take $80:8000 / 808000 / 0x...
Mesen's Lua sandbox must allow I/O and a controller must be in port 1: this writes settings.json
next to Mesen.exe (portable mode). Savestates are made inside an exec callback (Mesen requires it).
The Mesen folder is MESEN below or $MESEN.
"""
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import paths  # noqa: E402
import snes  # noqa: E402

MESEN = Path(os.environ.get('MESEN', Path(__file__).resolve().parents[2] / '_emulators/Mesen/Mesen.exe'))
MEM = {'wram': 'snesWorkRam', 'vram': 'snesVideoRam', 'cgram': 'snesCgRam', 'oam': 'snesSpriteRam',
       'rom': 'snesPrgRom', 'sram': 'snesSaveRam', 'bus': 'snesMemory'}
BUTTONS = {'a', 'b', 'x', 'y', 'l', 'r', 'start', 'select', 'up', 'down', 'left', 'right'}

LUA_HEAD = r'''
local OUT = %(out)s
local steps = %(steps)s
local MAXF = %(maxf)d
local i, f, wait, held, mash = 1, 0, 0, nil, nil
local tracefile, cbs = nil, {}
local function path(p) return OUT .. p end
local function hex(n, w) return string.format("%%0" .. (w or 6) .. "X", n) end
local function regs()
  local s = emu.getState()
  return hex(s["cpu.k"], 2) .. ":" .. hex(s["cpu.pc"], 4) .. " A=" .. hex(s["cpu.a"], 4) ..
    " X=" .. hex(s["cpu.x"], 4) .. " Y=" .. hex(s["cpu.y"], 4) .. " DB=" .. hex(s["cpu.dbr"], 2) .. " P=" .. hex(s["cpu.ps"], 2)
end
local function addtrace(kind, a, b, max)
  if not tracefile then tracefile = io.open(path("trace.txt"), "a") end
  local n = 0
  local id = emu.addMemoryCallback(function(addr, value)
    if n < max then
      n = n + 1
      tracefile:write(string.format("%%6d %%s %%s=%%02X %%s\n", f, kind, hex(addr), value or 0, regs()))
    end
  end, emu.callbackType[kind], a, b, emu.cpuType.snes, emu.memType.snesMemory)
  cbs[#cbs + 1] = {id, kind, a, b}
end
local function untrace()
  for _, c in ipairs(cbs) do emu.removeMemoryCallback(c[1], emu.callbackType[c[2]], c[3], c[4], emu.cpuType.snes, emu.memType.snesMemory) end
  cbs = {}
  if tracefile then tracefile:flush() end
end
local function finish(code)
  untrace()
  if tracefile then tracefile:close() end
  emu.stop(code)
end
emu.addEventCallback(function()
  if held then emu.setInput(held, 0) elseif mash and (f %% mash.every) < 3 then emu.setInput(mash.buttons, 0) end
end, emu.eventType.inputPolled)
emu.addEventCallback(function()
  f = f + 1
  if f > MAXF then finish(2) return end
  if wait > 0 then
    wait = wait - 1
    if wait == 0 then held = nil; mash = nil; if steps[i - 1] and steps[i - 1][1] == "press" then wait = -3 end end
    return
  end
  if wait < 0 then wait = wait + 1 return end
  while i <= #steps do
    local s = steps[i]; i = i + 1
    local op = s[1]
    if op == "wait" then wait = s[2] return
    elseif op == "press" then held = s[2]; wait = s[3] return
    elseif op == "mash" then mash = {buttons = s[2], every = s[4]}; wait = s[3] return
    elseif op == "shot" then local h = io.open(path(s[2] .. ".png"), "wb"); h:write(emu.takeScreenshot()); h:close()
    elseif op == "save" or op == "load" then
      -- savestates only work inside an exec callback: run once on the next instruction
      local id
      id = emu.addMemoryCallback(function()
        emu.removeMemoryCallback(id, emu.callbackType.exec, 0, 0xffffff, emu.cpuType.snes, emu.memType.snesMemory)
        if op == "save" then
          local h = io.open(path("states/" .. s[2] .. ".mss"), "wb"); h:write(emu.createSavestate()); h:close()
        else
          local h = io.open(path("states/" .. s[2] .. ".mss"), "rb"); emu.loadSavestate(h:read("a")); h:close()
        end
      end, emu.callbackType.exec, 0, 0xffffff, emu.cpuType.snes, emu.memType.snesMemory)
      wait = 1 return
    elseif op == "dump" then
      local h = io.open(path(s[5] .. ".bin"), "wb"); local mt = emu.memType[s[2]]
      local t = {}
      for a = s[3], s[3] + s[4] - 1 do t[#t + 1] = string.char(emu.read(a, mt, false)) end
      h:write(table.concat(t)); h:close()
    elseif op == "poke" then emu.write(s[2], s[3], emu.memType.snesMemory)
    elseif op == "write" then
      local h = io.open(s[4], "rb"); local b = h:read("a"); h:close(); local mt = emu.memType[s[2]]
      for k = 1, #b do emu.write(s[3] + k - 1, b:byte(k), mt) end
    elseif op == "trace" then addtrace(s[2], s[3], s[4], s[5])
    elseif op == "untrace" then untrace()
    elseif op == "regs" then
      local st = emu.getState(); local t = {}
      for k, v in pairs(st) do if k:sub(1, #s[2]) == s[2] then t[#t + 1] = k .. "=" .. tostring(v) end end
      table.sort(t); local h = io.open(path(s[3] .. ".txt"), "w"); h:write(table.concat(t, "\n")); h:close()
    elseif op == "cdl" then
      local c = emu.getCdlData(emu.memType.snesPrgRom); local t = {}
      for k = 1, #c do t[k] = string.char(c[k]) end
      local h = io.open(path(s[2] .. ".cdl"), "wb"); h:write(table.concat(t)); h:close()
    elseif op == "until" then
      if emu.read(s[2], emu.memType.snesMemory, false) ~= s[3] and s[4] > 0 then s[4] = s[4] - 1; i = i - 1 return end
    end
  end
  finish(0)
end, emu.eventType.endFrame)
'''


def winpath(p):
    return subprocess.run(['wslpath', '-w', str(p)], capture_output=True, text=True, check=True).stdout.strip()


def lua_str(s):
    return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'


def buttons(s):
    bs = set(s.lower().split('+'))
    if bs - BUTTONS:
        raise SystemExit(f'unknown button(s) {bs - BUTTONS}: use {" ".join(sorted(BUTTONS))}')
    return '{' + ', '.join(f'{b}=true' for b in sorted(bs)) + '}'


def addr(s):
    return snes.parse_addr(s)


def compile_step(line):
    w = line.split()
    op = w[0]
    if op == 'wait':
        return f'{{"wait", {int(w[1])}}}'
    if op == 'press':
        return f'{{"press", {buttons(w[1])}, {int(w[2]) if len(w) > 2 else 3}}}'
    if op == 'mash':
        return f'{{"mash", {buttons(w[1])}, {int(w[2])}, {int(w[3]) if len(w) > 3 else 12}}}'
    if op in ('shot', 'save', 'load'):
        return f'{{"{op}", {lua_str(w[1])}}}'
    if op == 'dump':
        return f'{{"dump", "{MEM[w[1]]}", {addr(w[2])}, {int(w[3], 0)}, {lua_str(w[4])}}}'
    if op == 'write':
        return f'{{"write", "{MEM[w[1]]}", {int(w[2], 0)}, {lua_str(winpath(w[3]))}}}'
    if op == 'poke':
        return f'{{"poke", {addr(w[1])}, {int(w[2], 0)}}}'
    if op == 'trace':
        return f'{{"trace", "{w[1]}", {addr(w[2])}, {addr(w[3])}, {int(w[4]) if len(w) > 4 else 2000}}}'
    if op == 'untrace':
        return '{"untrace"}'
    if op == 'regs':
        return f'{{"regs", {lua_str(w[1])}, {lua_str(w[2])}}}'
    if op == 'cdl':
        return f'{{"cdl", {lua_str(w[1])}}}'
    if op == 'until':
        return f'{{"until", {addr(w[1])}, {int(w[2], 0)}, {int(w[3]) if len(w) > 3 else 600}}}'
    raise SystemExit(f'unknown step: {line}')


def ensure_settings():
    s = MESEN.parent / 'settings.json'   # portable mode; headless runs need a controller in port 1
    if not s.exists() or 'SnesController' not in s.read_text():
        s.write_text('{ "Debug": { "ScriptWindow": { "AllowIoOsAccess": true } },\n'
                     '  "Snes": { "Port1": { "Type": "SnesController" } } }\n')


def run(steps, rom=None, out=None, max_frames=200000, quiet=False):
    """Run the steps; returns the exit status (0 = all steps done, 2 = frame limit)."""
    out = Path(out or paths.WORK / 'mesen').resolve()
    (out / 'states').mkdir(parents=True, exist_ok=True)
    trace = out / 'trace.txt'
    if trace.exists():
        trace.unlink()
    rom = Path(rom or paths.ROM).resolve()
    steps = [s.split('#')[0].strip() for s in steps]
    steps = [s for s in steps if s]
    lua = LUA_HEAD % {'out': lua_str(winpath(out) + '\\'), 'steps': '{' + ', '.join(map(compile_step, steps)) + '}',
                      'maxf': max_frames}
    script = out / 'run.lua'
    script.write_text(lua)
    ensure_settings()
    r = subprocess.run([str(MESEN), '--testrunner', winpath(rom), winpath(script)], cwd=MESEN.parent,
                       stdout=subprocess.DEVNULL)   # Mesen logs every uninitialised read
    if not quiet:
        print(f'mesen: exit {r.returncode}, output in {paths.show(out)}')
    return r.returncode


def main(argv=None):
    argv = paths.configure(sys.argv[1:] if argv is None else argv)
    rom = out = None
    maxf = 200000
    steps = []
    it = iter(argv)
    for a in it:
        if a == '--rom':
            rom = next(it)
        elif a == '--out':
            out = next(it)
        elif a == '--max-frames':
            maxf = int(next(it))
        elif a == '--file':
            steps += Path(next(it)).read_text().splitlines()
        elif a in ('-h', '--help'):
            sys.exit(__doc__)
        else:
            steps.append(a)
    if not steps:
        sys.exit(__doc__)
    sys.exit(run(steps, rom, out, maxf))


if __name__ == '__main__':
    main()
