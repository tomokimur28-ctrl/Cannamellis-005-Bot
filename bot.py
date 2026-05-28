import discord
from discord.ext import commands

bot = commands.Bot(command_prefix="/")

MAX_HP = 750
party = []
party_leader = None
game_active = False
enemy_hp = 2500
current_turn = 0
player_roles = {}
player_hp = {}
player_points = {}
buffs = {"role1_effect": False, "role3_buff": 0, "role4_debuff": False}

def assign_role(player):
    existing_roles = set(player_roles.values())
    for r in range(1, 5):
        if r not in existing_roles:
            player_roles[player] = r
            return r
    return None

def build_tmu():
    global enemy_hp, player_roles, player_hp
    ui = f"\n     TMU:\n     Target (= {enemy_hp} =)\n\n"
    line = ""
    for r in range(1, 5):
        target = None
        for p, role in player_roles.items():
            if role == r and p in party:
                target = p
                break
        if target:
            hp = player_hp[target]
            line += f"     {r} (= {hp} =)"
        else:
            line += f"     {r} (= --- =)"  # empty slot
    ui += line
    return ui

async def check_game_end(ctx):
    global game_active
    if enemy_hp <= 0:
        await ctx.send("🎉 The enemy is out of action! Players win!")
        for p, r in player_roles.items():
            if p in party:  # surviving players
                player_points[p] = player_points.get(p, 0) + 500
                await ctx.send(f"{p.mention} (Role {r}) earned 500 points! Total: {player_points[p]}")
        game_active = False
    elif len(party) == 0:
        await ctx.send("💀 All players are out of action. Enemy wins!")
        game_active = False

async def enemy_attack(ctx, last_actor):
    global party, player_hp
    if not party:
        return

    lowest_hp = min(player_hp[p] for p in party)
    candidates = [p for p in party if player_hp[p] == lowest_hp]

    if len(candidates) == len(party):
        target = last_actor
    else:
        target = candidates[0]

    dmg = 150
    player_hp[target] -= dmg
    await ctx.send(f"Status:\nEnemy attacks {target.mention} for {dmg} damage! HP: {player_hp[target]}")
    await ctx.send(build_tmu())

    if player_hp[target] <= 0:
        await ctx.send(f"{target.mention} is out of action!")
        party.remove(target)
        await check_game_end(ctx)

@bot.command(name="start")
async def start(ctx):
    global party, party_leader, game_active, enemy_hp, current_turn, player_roles, player_hp
    if not game_active:
        party = [ctx.author]
        party_leader = ctx.author
        game_active = True
        enemy_hp = 2500
        current_turn = 0
        player_roles = {ctx.author: 1}
        player_hp = {ctx.author: MAX_HP}
        await ctx.send(f"{ctx.author.mention} started a party! Use /join to join. Max 4 players.")
    else:
        if ctx.author == party_leader:
            await ctx.send(f"Game started with {len(party)} players! Enemy HP: {enemy_hp}")
            await ctx.send(f"It’s {party[current_turn].mention}'s turn! Type /action e or /action d.")
            await ctx.send(build_tmu())
        else:
            await ctx.send("Only the party leader can start the game.")

@bot.command(name="join")
async def join(ctx):
    global party, player_roles, player_hp
    if not game_active:
        await ctx.send("No active party. Use /start to create one.")
        return
    if len(party) >= 4:
        await ctx.send("Party is full.")
        return
    party.append(ctx.author)
    role = len(party)
    player_roles[ctx.author] = role
    player_hp[ctx.author] = MAX_HP
    await ctx.send(f"{ctx.author.mention} joined as Player {role} with {MAX_HP} HP!")
    await ctx.send(build_tmu())

@bot.command(name="leave")
async def leave(ctx):
    global party, game_active
    if ctx.author in party:
        party.remove(ctx.author)
        await ctx.send(f"{ctx.author.mention} left the party.")
        if len(party) == 0:
            game_active = False
            await ctx.send("No players left. The game has ended.")
    else:
        await ctx.send("You’re not in the party.")
    await ctx.send(build_tmu())

@bot.command(name="end")
async def end(ctx):
    global party, party_leader, game_active
    if ctx.author == party_leader:
        party = []
        party_leader = None
        game_active = False
        await ctx.send("The party has been disbanded. Game ended.")
    else:
        await ctx.send("Only the party leader can end the game.")

@bot.command(name="action")
async def action(ctx, choice: str, target_role: int = None):
    global enemy_hp, current_turn, buffs, player_hp, party
    if ctx.author != party[current_turn]:
        await ctx.send("It’s not your turn!")
        return

    if ctx.author not in player_roles:
        role = assign_role(ctx.author)
        await ctx.send(f"{ctx.author.mention} was auto-assigned Role {role}.")

    role = player_roles[ctx.author]
    dmg = 0

    if choice == "e":
        if role == 1:
            dmg = 100
            if buffs["role1_effect"]:
                dmg = 300
                buffs["role1_effect"] = False
        elif role == 2:
            dmg = 50
        elif role == 3:
            dmg = 25
        elif role == 4:
            dmg = 45

    elif choice == "d":
        if role == 1:
            buffs["role1_effect"] = True
            await ctx.send(f"{ctx.author.mention} is primed for a counterattack!")
        elif role == 2:
            target = None
            for p, r in player_roles.items():
                if r == target_role:
                    target = p
                    break
            if not target:
                await ctx.send("Invalid target role.")
            elif player_hp[target] >= MAX_HP:
                await ctx.send(f"{target.mention} is already at max HP ({MAX_HP}). Heal wasted!")
            else:
                healed_amount = min(100, MAX_HP - player_hp[target])
                player_hp[target] += healed_amount
                await ctx.send(f"{ctx.author.mention} healed {target.mention} for {healed_amount} HP! Current HP: {player_hp[target]}")
        elif role == 3:
            buffs["role3_buff"] = 2
            player_hp[ctx.author] = max(0, int(player_hp[ctx.author] * 0.75))
            await ctx.send("All players gain +50% damage for 2 turns! Player 3 sacrificed 25% HP.")
        elif role == 4:
            buffs["role4_debuff"] = True
            await ctx.send("Enemy is weakened! Takes +50% damage.")

    # Apply buffs/debuffs
    if dmg > 0:
        if buffs["role3_buff"] > 0:
            dmg = int(dmg * 1.5)
        if buffs["role4_debuff"]:
            dmg = int(dmg * 1.5)
        enemy_hp -= dmg
        await ctx.send(f"Status:\n{ctx.author.mention} dealt {dmg} damage! Enemy HP: {enemy_hp}")
        await ctx.send(build_tmu())

    # Check if enemy defeated
    await check_game_end(ctx)
    if not game_active:
        return

    # Enemy acts after Player 4
    last_actor = ctx.author
    if player_roles[ctx.author] == 4:
        await enemy_attack(ctx, last_actor)
        if not game_active:
            return

    # Cycle turn
    if party:
        current_turn = (current_turn + 1) % len(party)
        await ctx.send(f"It’s now {party[current_turn].mention}'s turn!")
        await ctx.send(build_tmu())

    # Reduce buff duration
    if buffs["role3_buff"] > 0:
        buffs["role3_buff"] -= 1

    # Check if current player died (failsafe)
    if player_hp[ctx.author] <= 0 and ctx.author in party:
        await ctx.send(f"{ctx.author.mention} is out of action!")
        party.remove(ctx.author)
        await check_game_end(ctx)

# --- Run the bot ---
bot.run("YOUR_BOT_TOKEN")
