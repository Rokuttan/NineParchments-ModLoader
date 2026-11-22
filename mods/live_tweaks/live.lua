-- Live tweaks: re-reads np_live.txt and applies the values to the types and to spells that already exist.
-- Line format:   Object.Property = value      (also accepts *1.5 and +10)
--                !dump                        (writes the player's spells to np_live_dump.txt)
-- Removed lines go back to the original value. The result of each read goes to np_live_status.txt.
local CFG = { file = 'np_live.txt', status = 'np_live_status.txt', dump = 'np_live_dump.txt', interval = 500 }

NPLive = NPLive or { raw = nil, applied = {}, original = {} }
local L = NPLive

local function readFile(path)
  local f = io.open(path, 'r')
  if not f then return nil end
  local s = f:read('*a'); f:close(); return s
end

local function getType(name)
  local t = typeManager:findTypeByName(name)
  if t == nil then error('type not found: ' .. name) end
  return t
end

local function propIndex(obj, prop)
  local i = obj:findPropertyIndexByName(prop)
  if i == nil or i < 0 then error(prop .. ' does not exist') end
  return i
end

-- Spells that exist right now (components already created from the type).
local function spellInstances()
  local out = {}
  local ok, chars = pcall(function() return common.CommonUtils.getSelectedLocalPlayerCharacters() end)
  if not ok or chars == nil then return out end
  local tm = getTypeManager()
  for _, ch in pairs(chars) do
    local casting = ch:findComponent(game.gameplay.skills.SpellCastingComponent)
    if casting ~= nil then
      local it = casting:findAllComponents(game.gameplay.skills.SpellBaseComponent)
      local c = it:next()
      while c ~= nil do
        local tn = tm:getTypeByUH(c:getType()):getName()
        out[#out + 1] = { name = tn, comp = c }
        c = it:next()
      end
    end
  end
  return out
end

local function setOn(obj, prop, v)
  local i = propIndex(obj, prop)
  obj:setPropertyValue(i, v)
  return obj:getPropertyValue(i)
end

local function apply(key, objName, prop, v, inst)
  local t = getType(objName)
  local back = setOn(t, prop, v)
  local n = 0
  for _, s in ipairs(inst) do
    if s.name == objName then pcall(setOn, s.comp, prop, v); n = n + 1 end
  end
  return back, n
end

local function parse(raw)
  local wanted, cmds, errs = {}, {}, {}
  for line in string.gmatch(raw .. '\n', '([^\n]*)\n') do
    line = string.gsub(string.gsub(line, '#.*$', ''), '^%s*(.-)%s*$', '%1')
    if line == '!dump' then cmds.dump = true
    elseif line ~= '' then
      local o, p, op, num = string.match(line, '^([%w_]+)%.([%w_]+)%s*=%s*([%*%+]?)%s*([%-%d%.eE]+)$')
      if o and tonumber(num) then wanted[o .. '.' .. p] = { o = o, p = p, op = op, v = tonumber(num) }
      else errs[#errs + 1] = 'invalid line: ' .. line end
    end
  end
  return wanted, cmds, errs
end

local function writeDump(inst)
  local f = io.open(CFG.dump, 'w'); if not f then return end
  local seen = {}
  f:write('-- spells of the local player(s) right now\n')
  for _, s in ipairs(inst) do
    if not seen[s.name] then
      seen[s.name] = true
      local line = s.name
      for _, p in ipairs({ 'BasePower', 'MaxStacks', 'CurrentStacks', 'RestoreStackTime', 'ProjectileSpeed' }) do
        local ok, v = pcall(function() local i = s.comp:findPropertyIndexByName(p); if i == nil or i < 0 then return nil end; return s.comp:getPropertyValue(i) end)
        if ok and v ~= nil then line = line .. '  ' .. p .. '=' .. tostring(v) end
      end
      f:write(line .. '\n')
    end
  end
  f:close()
end

local function sync(force)
  local raw = readFile(CFG.file) or ''
  if raw == L.raw and not force then return end
  L.raw = raw
  local wanted, cmds, report = parse(raw)
  local inst = spellInstances()
  -- 1) restore what was removed from the file
  for key, a in pairs(L.applied) do
    if wanted[key] == nil then
      local ok, err = pcall(apply, key, a.o, a.p, L.original[key], inst)
      report[#report + 1] = (ok and 'restored ' or 'ERROR restoring ') .. key .. ' = ' .. tostring(L.original[key]) .. (ok and '' or (': ' .. tostring(err)))
      L.applied[key] = nil
    end
  end
  -- 2) apply what is in the file (operations are relative to the ORIGINAL value)
  for key, w in pairs(wanted) do
    local ok, err = pcall(function()
      if L.original[key] == nil then
        local t = getType(w.o)
        L.original[key] = t:getPropertyValue(propIndex(t, w.p))
      end
      local base = L.original[key]
      local v = w.v
      if w.op == '*' then v = base * w.v elseif w.op == '+' then v = base + w.v end
      local back, n = apply(key, w.o, w.p, v, inst)
      L.applied[key] = w
      report[#report + 1] = 'ok ' .. key .. ': ' .. tostring(base) .. ' -> ' .. tostring(back) .. ' (type + ' .. n .. ' active spell(s))'
    end)
    if not ok then report[#report + 1] = 'ERROR ' .. key .. ': ' .. tostring(err) end
  end
  if cmds.dump then writeDump(inst); report[#report + 1] = 'spell list written to ' .. CFG.dump end
  local f = io.open(CFG.status, 'w')
  if f then local ok, now = pcall(os.date, '%H:%M:%S'); f:write('-- ' .. (ok and now or '?') .. '\n' .. table.concat(report, '\n') .. '\n'); f:close() end
  NPModLoader.log('live: ' .. #report .. ' line(s) processed')
end

-- New scene: spells were recreated, so re-apply everything once.
pcall(sync, true)
NPModLoader.every('live_tweaks', CFG.interval, function() sync(false) end)
