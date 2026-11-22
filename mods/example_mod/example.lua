-- Example script. Runs every time a scene (level, map menu...) finishes loading.
-- The game uses Lua 5.1: no goto, no //, nothing from Lua 5.2+.

-- Values from types.bin can be put into the code: the loader replaces the marker below with
-- the FINAL value (with the "*1.5" from mod.json already applied).
local FIREBALL_POWER = {{stat:FireballProjectileSpellComponent.BasePower}}

-- Global variables survive from one scene to the next (while the game stays open).
ExampleMod = ExampleMod or { scenes = 0 }
ExampleMod.scenes = ExampleMod.scenes + 1

-- Writes to the game log (<game folder>/log/nineparchments.log).
NPModLoader.log('example: scene ' .. ExampleMod.scenes .. ', Small Fireball power ' .. FIREBALL_POWER)

-- Writes the player's spells to a text file in the game folder.
local function listSpells()
  local f = io.open('np_example.txt', 'w')
  if not f then return end
  f:write('scenes loaded: ' .. ExampleMod.scenes .. '\n')
  local tm = getTypeManager()
  for _, character in pairs(common.CommonUtils.getSelectedLocalPlayerCharacters()) do
    local casting = character:findComponent(game.gameplay.skills.SpellCastingComponent)
    if casting ~= nil then
      local it = casting:findAllComponents(game.gameplay.skills.SpellBaseComponent)
      local spell = it:next()
      while spell ~= nil do
        local name = tm:getTypeByUH(spell:getType()):getName()
        local i = spell:findPropertyIndexByName('BasePower')
        f:write(name .. (i ~= nil and i >= 0 and ('  power=' .. tostring(spell:getPropertyValue(i))) or '') .. '\n')
        spell = it:next()
      end
    end
  end
  f:close()
end

-- Repeats every 5 seconds for as long as the scene lasts. Errors inside the function don't
-- crash the game: they show up in the log as "[modloader] error in ...".
NPModLoader.every('example_list', 5000, listSpells)
