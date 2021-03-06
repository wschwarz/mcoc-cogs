import re
from datetime import datetime, timedelta
from textwrap import wrap
from collections import UserDict, defaultdict
from math import log2
from math import *
from operator import attrgetter
import os
import time
import inspect
import aiohttp
import logging
import csv
import json
from gsheets import Sheets
import asyncio
from .utils.dataIO import dataIO
from functools import wraps
import discord
from discord.ext import commands
from .utils import chat_formatting as chat
from __main__ import send_cmd_help

logger = logging.getLogger('red.mcoc')
logger.setLevel(logging.INFO)


data_files = {
    'spotlight': {'remote': 'https://docs.google.com/spreadsheets/d/1I3T2G2tRV05vQKpBfmI04VpvP5LjCBPfVICDmuJsjks/pub?gid=0&single=true&output=csv',
                'local': 'data/mcoc/spotlight_data.csv', 'update_delta': 1},
    'crossreference': {'remote': 'https://docs.google.com/spreadsheets/d/1WghdD4mfchduobH0me4T6IvhZ-owesCIyLxb019744Y/pub?gid=0&single=true&output=csv',
                'local': 'data/mcoc/crossreference.csv', 'update_delta': 1},
    'prestigeCSV':{'remote': 'https://docs.google.com/spreadsheets/d/1I3T2G2tRV05vQKpBfmI04VpvP5LjCBPfVICDmuJsjks/pub?gid=1346864636&single=true&output=csv',
                'local': 'data/mcoc/prestige.csv', 'update_delta': 1},
    'phc_jpg' : {'remote': 'http://marvelbitvachempionov.ru/wp-content/dates_PCHen.jpg',
                'local': 'data/mcoc/dates_PCHen.jpg', 'update_delta': 7},
    'duelist' : {'remote': 'https://docs.google.com/spreadsheets/d/1LSNS5j1d_vs8LqeiDQD3lQFNIxQvTc9eAx3tNe5mdMk/pub?gid=1266181139&single=true&output=csv',
                'local': 'data/mcoc/duelist.csv', 'update_delta': 1},
    #'masteries' : {'remote':'https://docs.google.com/spreadsheets/d/1mEnMrBI5c8Tbszr0Zne6qHkW6WxZMXBOuZGe9XmrZm8/pub?gid=0&single=true&output=csv',
                #'local': 'data/mcoc/masteries.csv', 'update_delta': 1},
    }

local_files = {
    'sig_coeff': 'data/mcoc/sig_coeff.csv',
    'effect_keys': 'data/mcoc/effect_keys.csv',
}

gsheet_files = {
    'signature': {'gkey': '1kNvLfeWSCim8liXn6t0ksMAy5ArZL5Pzx4hhmLqjukg',
            'local': 'data/mcoc/sig_test.csv',
            'gid': 799981914,},
            #'payload': 'pub?gid=799981914&single=true&output=csv'},
    'spotlight': {'gkey': '1I3T2G2tRV05vQKpBfmI04VpvP5LjCBPfVICDmuJsjks',
            'local': 'data/mcoc/spotlight_test.csv',
            },
            #'payload': 'pub?gid=0&single=true&output=csv'},
    #'sig_coeff': {'gkey': '1kNvLfeWSCim8liXn6t0ksMAy5ArZL5Pzx4hhmLqjukg',
    'sig_coeff': {'gkey': '1P-GeEOyod6WSGq8fUfSPZcvowthNdy-nXLKOhjrmUVI',
            'local': 'data/mcoc/sig_co_test.csv',
            'stub': 'export',
            #'range': 'A1:N99',
            #'gid': 696682690},
            },
    'crossreference': {'gkey': '1QesYLjDC8yd4t52g4bN70N8FndJXrrTr7g7OAS0BItk',
            'local': 'data/mcoc/xref_test.csv',
            #'payload': 'export?format=csv'}
            },
            #'payload': 'pub?gid=0&single=true&output=csv'}
}

star_glyph = '★'
lolmap_path='data/mcoc/maps/lolmap.png'
file_checks_json = 'data/mcoc/file_checks.json'
remote_data_basepath = 'https://raw.githubusercontent.com/JasonJW/mcoc-cogs/master/mcoc/data/'
icon_sdf = 'https://raw.githubusercontent.com/JasonJW/mcoc-cogs/master/mcoc/data/sdf_icon.png'

###### KEYS for MCOC JSON Data Extraction
mcoc_dir='data/mcoc/com.kabam.marvelbattle/files/xlate/snapshots/en/'
kabam_bio = mcoc_dir + 'character_bios_en.json'
kabam_special_attacks = mcoc_dir+ 'special_attacks_en.json'
kabam_bcg_stat_en = mcoc_dir+'bcg_stat_en.json'
##### Special attacks require:
## mcoc_files + mcoc_special_attack + <champ.mcocjson> + {'_0','_1','_2'} ---> Special Attack title
#mcoc_special_attack='ID_SPECIAL_ATTACK_'
## mcoc_files mcoc_special_attack_desc + <champ.mcocjson> + {'_0','_1','_2'} ---> Special Attack Short description
#mcoc_special_attack_desc='ID_SPECIAL_ATTACK_DESCRIPTION_'


class_color_codes = {
        'Cosmic': discord.Color(0x2799f7), 'Tech': discord.Color(0x0033ff),
        'Mutant': discord.Color(0xffd400), 'Skill': discord.Color(0xdb1200),
        'Science': discord.Color(0x0b8c13), 'Mystic': discord.Color(0x7f0da8),
        'All': discord.Color(0xffffff), 'default': discord.Color.light_grey(),
        }
class_emoji = {
        'All':'<:all2:339511715920084993>',
        'Cosmic':'<:cosmic2:339511716104896512>',
        'Tech':'<:tech2:339511716197171200>',
        'Mutant':'<:mutant2:339511716201365514>',
        'Skill':'<:skill2:339511716549230592>',
        'Science':'<:science2:339511716029267969>',
        'Mystic':'<:mystic2:339511716150771712>',
        }

def from_flat(flat, ch_rating):
    denom = 5 * ch_rating + 1500 + flat
    return round(100*flat/denom, 2)

def to_flat(per, ch_rating):
    num = (5 * ch_rating + 1500) * per
    return round(num/(100-per), 2)

class QuietUserError(commands.UserInputError):
    pass

class AmbiguousArgError(QuietUserError):
    pass

class ChampConverter(commands.Converter):
    '''Argument Parsing class that geneartes Champion objects from user input'''

    arg_help = '''
    Specify a single champion with optional parameters of star, rank, or sig.
    Champion names can be a number of aliases or partial aliases if no conflicts are found.

    The optional arguments can be in any order, with or without spaces.
        <digit>* specifies star <default: 4>
        r<digit> specifies rank <default: 5>
        s<digit> specifies signature level <default: 99>

    Examples:
        4* yj r4 s30  ->  4 star Yellowjacket rank 4/40 sig 30
        r35*im        ->  5 star Ironman rank 3/45 sig 99
        '''

    _bare_arg = None
    parse_re = re.compile(r'''(?:s(?P<sig>[0-9]{1,3}))
                             |(?:r(?P<rank>[1-5]))
                             |(?:(?P<star>[1-5])\\?\*)
                             |(?:d(?P<debug>[0-9]{1,2}))''', re.X)
    async def convert(self):
        bot = self.ctx.bot
        attrs = {}
        if self._bare_arg:
            args = self.argument.rsplit(' ', maxsplit=1)
            if len(args) > 1 and args[-1].isdecimal():
                attrs[self._bare_arg] = int(args[-1])
                self.argument = args[0]
        arg = ''.join(self.argument.lower().split(' '))
        for m in self.parse_re.finditer(arg):
            attrs[m.lastgroup] = int(m.group(m.lastgroup))
        token = self.parse_re.sub('', arg)
        if not token:
            err_str = "No Champion remains from arg '{}'".format(self.argument)
            await bot.say(err_str)
            raise commands.BadArgument(err_str)
        return (await self.get_champion(bot, token, attrs))

    async def get_champion(self, bot, token, attrs):
        mcoc = bot.get_cog('MCOC')
        try:
            champ = await mcoc.get_champion(token, attrs)
        except KeyError:
            champs = await mcoc.search_champions('.*{}.*'.format(token), attrs)
            if len(champs) == 1:
                await bot.say("'{}' was not exact but found close alternative".format(
                        token))
                champ = champs[0]
            elif len(champs) > 1:
                em = discord.Embed(title='Ambiguous Argument "{}"'.format(token),
                        description='Resolved to multiple possible champs')
                for champ in champs:
                    em.add_field(name=champ.full_name, inline=False,
                            value=chat.box(', '.join(champ.alias_set)))
                await bot.say(embed=em)
                raise AmbiguousArgError('Multiple matches for arg "{}"'.format(token))
            else:
                err_str = "Cannot resolve alias for '{}'".format(token)
                await bot.say(err_str)
                raise commands.BadArgument(err_str)
        return champ

class ChampConverterSig(ChampConverter):
    _bare_arg = 'sig'
    arg_help = ChampConverter.arg_help + '''
    Bare Number argument for this function is sig level:
        "yjr5s30" is equivalent to "yjr5 30"'''

class ChampConverterRank(ChampConverter):
    _bare_arg = 'rank'
    arg_help = ChampConverter.arg_help + '''
    Bare Number argument for this function is rank:
        "yjr5s30" is equivalent to "yjs30 5"'''

class ChampConverterStar(ChampConverter):
    _bare_arg = 'star'
    arg_help = ChampConverter.arg_help + '''
    Bare Number argument for this function is star:
        "5*yjr5s30" is equivalent to "yjr5s30 5"'''

class ChampConverterDebug(ChampConverter):
    _bare_arg = 'debug'

class ChampConverterMult(ChampConverter):

    arg_help = '''
    Specify multiple champions with optional parameters of star, rank, or sig.
    Champion names can be a number of aliases or partial aliases if no conflicts are found.

    The optional arguments can be in any order.
        <digit>* specifies star <default: 4>
        r<digit> specifies rank <default: 5>
        s<digit> specifies signature level <default: 99>

    If optional arguments are listed without a champion, it changes the default for all
    remaining champions.  Arguments attached to a champion are local to that champion
    only.

    Examples:
        s20 yj im        ->  4* Yellowjacket r5/50 sig 20, 4* Ironman r5/50 sig 20
        r35*ims20 ims40  ->  5 star Ironman r3/45 sig 20, 4* Ironman r5/50 sig 40
        r4s20 yj ims40 lc -> 4* Yellowjacket r4/40 sig 20, 4* Ironman r4/40 sig 40, 4* Luke Cage r4/40 sig 20
        '''

    async def convert(self):
        bot = self.ctx.bot
        champs = []
        default = {}
        for arg in self.argument.lower().split(' '):
            attrs = default.copy()
            for m in self.parse_re.finditer(arg):
                attrs[m.lastgroup] = int(m.group(m.lastgroup))
            token = self.parse_re.sub('', arg)
            if token != '':
                champ = await self.get_champion(bot, token, attrs)
                champs.append(champ)
            else:
                default.update(attrs)
        return champs

class AliasDict(UserDict):
    '''Custom dictionary that uses a tuple of aliases as key elements.
    Item addressing is handled either from the tuple as a whole or any
    element within the tuple key.
    '''
    def __getitem__(self, key):
        if key in self.data:
            return self.data[key]
        for k in self.data.keys():
            if key in k:
                return self.data[k]
        raise KeyError("Invalid Key '{}'".format(key))

class ChampionFactory():
    '''Creation and storage of the dynamically created Champion subclasses.
    A new subclass is created for every champion defined.  Then objects are
    created from user function calls off of the dynamic classes.'''

    def __init__(self, *args, **kwargs):
        self.cooldown_delta = 5 * 60
        self.cooldown = time.time() - self.cooldown_delta - 1
        self.needs_init = True
        super().__init__(*args, **kwargs)
        logger.debug('ChampionFactory Init')

    def init(self):
        logger.info('Preparing data structures')
        self._prepare_aliases()
        self._prepare_prestige_data()
        self.needs_init = False

    async def update_local(self):
        now = time.time()
        if now - self.cooldown_delta < self.cooldown:
            return
        self.cooldown = now
        is_updated = await self.verify_cache_remote_files()
        if is_updated or self.needs_init:
            self.init()

    def create_champion_class(self, bot, alias_set, **kwargs):
        kwargs['bot'] = bot
        kwargs['alias_set'] = alias_set
        kwargs['klass'] = kwargs.pop('class', 'default')

        kwargs['full_name'] = kwargs['champ']
        kwargs['bold_name'] = chat.bold(' '.join(
                [word.capitalize() for word in kwargs['full_name'].split(' ')]))
        kwargs['class_color'] = class_color_codes[kwargs['klass']]
        kwargs['class_icon'] = class_emoji[kwargs['klass']]

        kwargs['class_tags'] = {'#' + kwargs['klass'].lower()}
        for a in kwargs['abilities'].split(','):
            kwargs['class_tags'].add('#' + ''.join(a.lower().split(' ')))
        for a in kwargs['hashtags'].split('#'):
            kwargs['class_tags'].add('#' + ''.join(a.lower().split(' ')))
        if kwargs['class_tags']:
            kwargs['class_tags'].difference_update({'#'})

        for key, value in kwargs.items():
            if not value or value == 'n/a':
                kwargs[key] = None

        champion = type(kwargs['mattkraftid'], (Champion,), kwargs)
        self.champions[tuple(alias_set)] = champion
        logger.debug('Creating Champion class {}'.format(kwargs['mattkraftid']))
        return champion

    async def get_champion(self, name_id, attrs=None):
        '''straight alias lookup followed by new champion object creation'''
        await self.update_local()
        return self.champions[name_id](attrs)

    async def search_champions(self, search_str, attrs=None):
        '''searching through champion aliases and allowing partial matches.
        Returns an array of new champion objects'''
        await self.update_local()
        re_str = re.compile(search_str)
        champs = []
        for champ in self.champions.values():
            if any([re_str.search(alias) is not None
                    for alias in champ.alias_set]):
                champs.append(champ(attrs))
        return champs

    async def verify_cache_remote_files(self, verbose=False, force_cache=False):
        logger.info('Check remote files')
        if os.path.exists(file_checks_json):
            try:
                file_checks = dataIO.load_json(file_checks_json)
            except:
                file_checks = {}
        else:
            file_checks = {}
        async with aiohttp.ClientSession() as s:
            is_updated = False
            for key in data_files.keys():
                if key in file_checks:
                    last_check = datetime(*file_checks.get(key))
                else:
                    last_check = None
                remote_check = await self.cache_remote_file(key, s, verbose=verbose,
                        last_check=last_check)
                if remote_check:
                    is_updated = True
                    file_checks[key] = remote_check.timetuple()[:6]
        dataIO.save_json(file_checks_json, file_checks)
        return is_updated

    async def cache_remote_file(self, key, session, verbose=False, last_check=None,
                force_cache=False):
        dargs = data_files[key]
        strf_remote = '%a, %d %b %Y %H:%M:%S %Z'
        response = None
        remote_check = False
        now = datetime.now()
        if os.path.exists(dargs['local']) and not force_cache:
            if last_check:
                check_marker = now - timedelta(days=dargs['update_delta'])
                refresh_remote_check = check_marker > last_check
            else:
                refresh_remote_check = True
            local_dt = datetime.fromtimestamp(os.path.getmtime(dargs['local']))
            if refresh_remote_check:
                response = await session.get(dargs['remote'])
                if 'Last-Modified' in response.headers:
                    remote_dt = datetime.strptime(response.headers['Last-Modified'], strf_remote)
                    remote_check = now
                    if remote_dt < local_dt:
                        # Remote file is older, so no need to transfer
                        response = None
        else:
            response = await session.get(dargs['remote'])
        if response and response.status == 200:
            logger.info('Caching ' + dargs['local'])
            with open(dargs['local'], 'wb') as fp:
                fp.write(await response.read())
            remote_check = now
            await response.release()
        elif response:
            err_str = "HTTP error code {} while trying to retrieve {}".format(
                    response.status, key)
            logger.error(err_str)
            await response.release()
        elif verbose and remote_check:
            logger.info('Local file up-to-date:', dargs['local'], now)
        return remote_check

    def _prepare_aliases(self):
        '''Create a python friendly data structure from the aliases json'''
        logger.debug('Preparing aliases')
        self.champions = AliasDict()
        raw_data = load_csv(data_files['crossreference']['local'])
        champs = []
        all_aliases = set()
        id_index = raw_data.fieldnames.index('status')
        alias_index = raw_data.fieldnames[:id_index]
        for row in raw_data:
            if all([not i for i in row.values()]):
                continue    # empty row check
            alias_set = set()
            for col in alias_index:
                if row[col]:
                    alias_set.add(row[col].lower())
            if all_aliases.isdisjoint(alias_set):
                all_aliases.union(alias_set)
            else:
                raise KeyError("There are aliases that conflict with previous aliases."
                        + "  First occurance with champ {}.".format(row['champ']))
            self.create_champion_class(self.bot, alias_set, **row)

    def _prepare_prestige_data(self):
        logger.debug('Preparing prestige')
        mattkraft_re = re.compile(r'(?P<star>\d)-(?P<champ>.+)-(?P<rank>\d)')
        with open(data_files['prestigeCSV']['local'], newline='') as csvfile:
            reader = csv.reader(csvfile)
            for row in reader:
                champ_match = mattkraft_re.fullmatch(row.pop(0))
                if not champ_match:
                    continue
                name = champ_match.group('champ')
                star = int(champ_match.group('star'))
                rank = int(champ_match.group('rank'))

                champ = self.champions.get(name)
                if not champ:
                    logger.info('Skipping ' + name)
                    continue

                sig_len = 201 if star == 5 else 100
                sig = [0] * sig_len
                for i, v in enumerate(row):
                    try:
                        if v and i < sig_len:
                            sig[i] = int(v)
                    except:
                        print(name, i, v, len(sig))
                        raise
                if not hasattr(champ, 'prestige_data'):
                    champ.prestige_data = {4: [None] * 5, 5: [None] * 5}
                try:
                    champ.prestige_data[star][rank-1] = sig
                except:
                    print(name, star, rank, len(champ.prestige_data),
                            len(champ.prestige_data[star]))
                    raise

def command_arg_help(**cmdkwargs):
    def internal_func(f):
        helps = []
        for param in inspect.signature(f).parameters.values():
            if issubclass(param.annotation, commands.Converter):
                arg_help = getattr(param.annotation, 'arg_help')
                if arg_help is not None:
                    helps.append(arg_help)
        if helps:
            if f.__doc__:
                helps.insert(0, f.__doc__)
            f.__doc__ = '\n'.join(helps)
        @wraps(f)
        async def wrapper(*args, **kwargs):
            return await f(*args, **kwargs)
        return commands.command(**cmdkwargs)(wrapper)
    return internal_func

class MCOC(ChampionFactory):
    '''A Cog for Marvel's Contest of Champions'''

    def __init__(self, bot):
        self.bot = bot

        self.settings = {
                'siglvl': 1,
                'sigstep': 20,
                'table_width': 9,
                'sig_inc_zero': False,
                }

        self.parse_re = re.compile(r'(?:s(?P<sig>[0-9]{1,3}))|(?:r(?P<rank>[1-5]))|(?:(?P<star>[1-5])\\?\*)')
        self.split_re = re.compile(', (?=\w+:)')
        logger.info("MCOC Init")
        super().__init__()

    @commands.command(aliases=('p2f',), hidden=True)
    async def per2flat(self, per: float, ch_rating: int=100):
        '''Convert Percentage to MCOC Flat Value'''
        await self.bot.say(to_flat(per, ch_rating))

    @commands.command(name='flat', aliases=('f2p'))
    async def flat2per(self, *, m):
        '''Convert MCOC Flat Value to Percentge'''
        if ' ' in m:
            m, cr = m.rsplit(' ',1)
            challenger_rating = int(cr)
        else:
            challenger_rating = 100
        m = ''.join(m)
        math_filter = re.findall(r'[\[\]\-()*+/0-9=.,% ]' +
            r'|acos|acosh|asin|asinh' +
            r'|atan|atan2|atanh|ceil|copysign|cos|cosh|degrees|e|erf|erfc|exp' +
            r'|expm1|fabs|factorial|floor|fmod|frexp|fsum|gamma|gcd|hypot|inf' +
            r'|isclose|isfinite|isinf|isnan|round|ldexp|lgamma|log|log10|log1p' +
            r'|log2|modf|nan|pi|pow|radians|sin|sinh|sqrt|tan|tanh', m)
        flat_val = eval(''.join(math_filter))
        p = from_flat(flat_val, challenger_rating)
        em = discord.Embed(color=discord.Color.gold(),
                title='FlatValue:',
                description='{}'.format(flat_val))
        em.add_field(name='Percentage:', value='{}\%'.format(p))
        await self.bot.say(embed=em)

    @commands.command(aliases=('compf','cfrac'), hidden=True)
    async def compound_frac(self, base: float, exp: int):
        '''Calculate multiplicative compounded fractions'''
        if base > 1:
            base = base / 100
        compound = 1 - (1 - base)**exp
        em = discord.Embed(color=discord.Color.gold(),
            title="Compounded Fractions",
            description='{:.2%} compounded {} times'.format(base, exp))
        em.add_field(name='Expected Chance', value='{:.2%}'.format(compound))
        await self.bot.say(embed=em)

    @commands.command(aliases=('update_mcoc',), hidden=True)
    async def mcoc_update(self, fname, force=False):
        if len(fname) > 3:
            for key in data_files.keys():
                if key.startswith(fname):
                    fname = key
                    break
        if fname in data_files:
            async with aiohttp.ClientSession() as s:
                await self.cache_remote_file(fname, s, force_cache=force, verbose=True)
        else:
            await self.bot.say('Valid options for 1st argument are one of (or initial portion of)\n\t'
                    + '\n\t'.join(data_files.keys()))
            return

        self.init()
        await self.bot.say('Summoner, I have Collected the data')

    async def say_user_error(self, msg):
        em = discord.Embed(color=discord.Color.gold(), title=msg)
        await self.bot.say(embed=em)

    @commands.command(hidden=True)
    async def mcocset(self, setting, value):
        if setting in self.settings:
            self.settings[setting] = int(value)

    @commands.command(hidden=True)
    async def cache_gsheets(self):
        s = await aiohttp.ClientSession()
        #gs = Sheets.from_files('data/mcoc/client_secrets.json')
        for k, v in gsheet_files.items():
            #s = gs[v['gkey']]
            #s.sheets[0].to_csv(v['local'])
            #payload = {'format': 'csv', 'gid': v.get('gid', 0)}
            if 'payload' in k:
                payload = {}
                remote = 'https://docs.google.com/spreadsheets/d/{0[gkey]}/{0[payload]}'.format(v)
            elif v.get('stub') == 'export':
                payload = {'format': 'csv', 'gid': v.get('gid', 0)}
                remote = 'https://docs.google.com/spreadsheets/d/{0[gkey]}/{0[stub]}'.format(v)
            else:
                payload = {'output': 'csv', 'single': 'true', 'gid': v.get('gid', 0)}
                remote = 'https://docs.google.com/spreadsheets/d/{0}/pub'.format(v['gkey'])
            #response = s.get(remote)
            response = await s.get(remote, params=payload)
            if response.status == 200:
                with open(v['local'], 'wb') as fp:
                    fp.write(await response.read())
            else:
                err_str = "HTTP error code {} while trying to retrieve Google Sheet {}".format(
                        response.status, k)
                await self.bot.say(err_str)
        await self.bot.say("Google Sheet retrieval complete")

    @commands.group(pass_context=True)
    async def champ(self, ctx):
        if ctx.invoked_subcommand is None:
            try:
                await command_arg_help(ctx)
            except:
                print('command_arg_help failed')
                await send_cmd_help(ctx)
            return

    @champ.command(name='featured')
    async def champ_featured(self, champ : ChampConverter):
        '''Retrieve Champion Feature Images'''
        em = discord.Embed(color=champ.class_color, title=champ.bold_name)
        em.set_author(name=champ.full_name + ' - ' + champ.short, icon_url=champ.get_avatar())
        em.set_image(url=champ.get_featured())
        await self.bot.say(embed=em)

    @champ.command(name='portrait')
    async def champ_portrait(self, champ : ChampConverter):
        '''Retrieve Champion Portrait'''
        em = discord.Embed(color=champ.class_color, title=champ.bold_name)
        em.set_author(name=champ.full_name + ' - ' + champ.short, icon_url=champ.get_avatar())
        em.set_image(url=champ.get_avatar())
        await self.bot.say(embed=em)

    @champ.command(name='bio', aliases=('biography',))
    async def champ_bio(self, *, champ : ChampConverterDebug):
        '''Retrieve the Bio of a Champion'''
        try:
            bio_desc = await champ.get_bio()
        except KeyError:
            await self.say_user_error("Cannot find bio for Champion '{}'".format(champ.full_name))
            return
        em = discord.Embed(color=champ.class_color, title='Champion Biography',
                description=bio_desc)
        em.set_author(name=champ.full_name, icon_url=champ.get_avatar())
        em.add_field(name='hashtags',
                value=chat.box(' '.join(champ.class_tags.union(champ.tags))))
        em.add_field(name='Shortcode', value=champ.short)
        em.set_thumbnail(url=champ.get_avatar())
        em.set_footer(text='MCOC Game Files', icon_url='https://imgur.com/UniRf5f.png')
        await self.bot.say(embed=em)

    @champ.command(name='duel')
    async def champ_duel(self, champ : ChampConverter):
        '''Lookup Duel/Sparring Targets'''
        dataset=data_files['duelist']['local']
        # targets = defaultdict(list)
        targets = []
        # names = {4: 'Duel', 5: 'Sparring'}
        em = discord.Embed(color=champ.class_color, title='')
        em.set_author(name=champ.full_name, icon_url=champ.get_avatar())
        em.set_image(url=champ.get_featured())
        em.set_footer(text='Sourced from Community Spreadsheet',
                icon_url='https://d2jixqqjqj5d23.cloudfront.net/assets/developer/imgs/icons/google-spreadsheet-icon.png')
        target_found = False
        for star in (4,5):
            for rank in range(1,5):
                key = '{}-{}-{}'.format(star, champ.mattkraftid, rank)
                for data in get_csv_rows(dataset, 'unique', key):#champ.unique):
                    if data['username'] != 'none':
                        targets.append( '{}{} {} {} : {}'.format(star, star_glyph, data['maxlevel'], champ.full_name, data['username']))
        if len(targets) > 0:
            em.add_field(name='Duel Targets', value='\n'.join(targets),inline=False)
                # em.add_field(name='{} Target'.format(names[star]),
                #         value='\n'.join(k for k in targets[star]), inline=False)
        else:
            em.add_field(name='Target not found',
                    value='\n'.join(['Add one to the Community Spreadhseet!',
                            'Duel Targets: <http://simians.tk/mcocduel>',
                            'Sparring Targets: <http://simians.tk/mcocspar>']))
        em.add_field(name='Shortcode', value=champ.short, inline=False)
        await self.bot.say(embed=em)

    @champ.command(name='about', aliases=('champ_stat', 'champ_stats', 'cstat', 'about_champ',))
    async def champ_about(self, *, champ : ChampConverterRank):
        '''Retrieve Champion Base Stats'''
        data = champ.get_spotlight(default='x')
        title = 'Base Attributes for {}'.format(champ.verbose_str)
        em = discord.Embed(color=champ.class_color,
                title='Base Attributes')
        em.set_author(name=champ.verbose_str, icon_url=champ.get_avatar())
        titles = ('Health', 'Attack', 'Crit Rate', 'Crit Dmg', 'Armor', 'Block Prof')
        keys = ('health', 'attack', 'critical', 'critdamage', 'armor', 'blockprof')
        xref = get_csv_row(data_files['crossreference']['local'],'champ',champ.full_name)

        if champ.debug:
            em.add_field(name='Attrs', value='\n'.join(titles))
            em.add_field(name='Values', value='\n'.join([data[k] for k in keys]), inline=True)
            em.add_field(name='Added to PHC', value=xref['4basic'])
        else:
            stats = [[titles[i], data[keys[i]]] for i in range(len(titles))]
            em.add_field(name='Base Stats',
                value=tabulate(stats, width=11, rotate=False, header_sep=False))
        # em.add_field(name='Feature Crystal', value=xref['released'],inline=False)
        # em.add_field(name='4'+star_glyph+' Crystal & \nPremium Hero Crystal', value=xref['4basic'],inline=False)
        # em.add_field(name='5'+star_glyph+' Crystal', value=xref['5subfeature'],inline=False)
        # state = xref['f/s/b']
        # if state == 'b':
        #     em.add_field(name='Basic 4'+star_glyph+' Chance', value=xref['4chance'],inline=False)
        #     em.add_field(name='Basic 5'+star_glyph+' Chance', value=xref['5chance'],inline=False)
        # elif state == 's':
        #     em.add_field(name='Basic 4'+star_glyph+' Chance', value=xref['4chance'],inline=False)
        #     em.add_field(name='Featured 5'+star_glyph+' Chance', value=xref['5chance'],inline=False)
        # elif state == 'f':
        #     em.add_field(name='Featured 4'+star_glyph+' Chance', value=xref['5chance'],inline=False)
        #     em.add_field(name='Featured 5'+star_glyph+' Chance', value=xref['5chance'],inline=False)
        if champ.infopage != 'none':
            em.add_field(name='Infopage',value='<{}>'.format(champ.infopage),inline=False)
        else:
            em.add_field(name='Infopage',value='No spotlight post from Kabam',inline=False)
            em.add_field(name='hashtags',
                    value=chat.box(' '.join(champ.class_tags.union(champ.tags))))
        em.add_field(name='Shortcode', value=champ.short)
        em.set_footer(text='[-SDF-] Spotlight Dataset', icon_url=icon_sdf)
        em.set_thumbnail(url=champ.get_avatar())
        await self.bot.say(embed=em)

    @champ.command(name='released', aliases=('odds','chances',))
    async def champ_released(self, *, champs : ChampConverterMult):
        '''Retrieve Champion Release Date'''
        for champ in champs:
            xref = get_csv_row(data_files['crossreference']['local'],'champ',champ.full_name)
            em = discord.Embed(color=champ.class_color,
                    title='Release Dates & Est. Pull Chance')
            em.set_author(name=champ.full_name, icon_url=champ.get_avatar())
            em.add_field(name='Feature Crystal', value=xref['released'],inline=False)
            em.add_field(name='4'+star_glyph+' Crystal & \nPremium Hero Crystal', value=xref['4basic'],inline=False)
            em.add_field(name='5'+star_glyph+' Crystal', value=xref['5subfeature'],inline=False)
            state = xref['f/s/b']
            if state == 'b':
                em.add_field(name='Basic 4'+star_glyph+' Chance', value=xref['4chance'],inline=False)
                em.add_field(name='Basic 5'+star_glyph+' Chance', value=xref['5chance'],inline=False)
            elif state == 's':
                em.add_field(name='Basic 4'+star_glyph+' Chance', value=xref['4chance'],inline=False)
                em.add_field(name='Featured 5'+star_glyph+' Chance', value=xref['5chance'],inline=False)
            elif state == 'f':
                em.add_field(name='Featured 4'+star_glyph+' Chance', value=xref['4chance'],inline=False)
                em.add_field(name='Featured 5'+star_glyph+' Chance', value=xref['5chance'],inline=False)
            em.add_field(name='Shortcode', value=champ.short)
            em.set_thumbnail(url=champ.get_featured())
            em.set_footer(text='[-SDF-] Spotlight Dataset', icon_url=icon_sdf)
            await self.bot.say(embed=em)

    @champ.command(name='sig', aliases=['signature',])
    async def champ_sig(self, *, champ : ChampConverterSig):
        '''Retrieve the Signature Ability of a Champion'''
        if champ.star == 5:
            await self.say_user_error("Sorry.  5{} data for any champion is not currently available".format(star_glyph))
            return
        try:
            title, desc, sig_calcs = await champ.process_sig_description()
        except KeyError:
            await champ.missing_sig_ad()
            return
        if title is None:
            return
        em = discord.Embed(color=champ.class_color, title='Signature Ability')
        em.set_author(name=champ.full_name, icon_url=champ.get_avatar())
        em.add_field(name=title, value=champ.star_str)
        em.add_field(name='Signature Level {}'.format(champ.sig),
                value=desc.format(d=sig_calcs))
        em.add_field(name='Shortcode', value=champ.short)
        em.set_footer(text='MCOC Game Files', icon_url='https://imgur.com/UniRf5f.png')
        em.set_thumbnail(url=champ.get_avatar())
        await self.bot.say(embed=em)

    @commands.command(hidden=True)
    async def dump_sigs(self):
        with open('sig_data_4star.json', encoding='utf-8', mode="w") as fp:
            #jenc = json.JSONEncoder(indent='\t', sort_keys=True)
            reader = load_csv(local_files['effect_keys'])
            dump = {}
            for c, row in enumerate(reader):
                #if c < 75 or c > 90:
                    #continue
                champ = await self.get_champion(row['CHAMP'].lower())
                item = {'name': champ.full_name, 'sig_data': []}
                for i in range(1, 100):
                    champ.update_attrs({'sig': i})
                    try:
                        title, desc, sig_calcs = await champ.process_sig_description(quiet=True)
                    except KeyError:
                        break
                    if sig_calcs is None:
                        break
                    if i == 1:
                        item['title'] = title
                        item['description'] = desc
                        item['star_rank'] = champ.star_str
                    item['sig_data'].append(sig_calcs)
                if not item['sig_data']:
                    continue
                #fp.write(jenc.encode(item))
                dump[champ.mattkraftid] = item
                print(champ.full_name)
            json.dump(dump, fp, indent='\t', sort_keys=True)
        await self.bot.say('Hopefully dumped')

    @commands.command(hidden=True)
    async def json_sig(self, *, champ : ChampConverterSig):
        if champ.star != 4 or champ.rank != 5:
            await self.bot.say('This function only checks 4* rank5 champs')
            return
        jfile = dataIO.load_json('sig_data_4star.json')
        title, desc, sig_calcs = await champ.process_sig_description(quiet=True)
        jsig = jfile[champ.mattkraftid]
        em = discord.Embed(title='Check for {}'.format(champ.full_name))
        em.add_field(name=jsig['title'],
                value=jsig['description'].format(d=jsig['sig_data'][champ.sig-1]))
        await self.bot.say(embed=em)
        assert title == jsig['title']
        assert desc == jsig['description']
        assert sig_calcs == jsig['sig_data'][champ.sig-1]

    @champ.command(name='info', aliases=('infopage',))
    async def champ_info(self, *, champ : ChampConverterDebug):
        '''Retrieve Champion Spotlight link if available'''
        em = discord.Embed(color=champ.class_color, title='Kabam Spotlight',)
        em.set_author(name=champ.full_name, icon_url=champ.get_avatar())
        if champ.infopage == 'none':
            em.add_field(name=champ.full_name, value='No URL found')
        else:
            em.add_field(name=champ.full_name, value=champ.infopage)
        em.add_field(name='Shortcode', value=champ.short)
        em.set_footer(text='MCOC Website', icon_url='https://imgur.com/UniRf5f.png')
        em.set_thumbnail(url=champ.get_avatar())
        await self.bot.say(embed=em)

    @champ.command(name='abilities')
    async def champ_abilities(self, champ : ChampConverter):
        '''In-Development: Retrieve Champion Abilities'''
        specials = champ.get_special_attacks()
        em.set_author(name=champ.full_name, icon_url=champ.get_avatar())
        em = discord.Embed(color=champ.class_color, title='Champion Abilities')
        # em.add_field(name='Passive',value='placeholder')
        # em.add_field(name='All Attacks',value='placeholder')
        # em.add_field(name='When Attacked',value='placeholder')
        row=get_csv_row(data_files['crossreference']['local'],'champ',champ.full_name)
        abilities=row['abilities'].split(', ')
        hashtags=row['hashtags'].split(' #')
        em.add_field(name='Abilities', value='\n'.join(abilities))
        em.add_field(name='Hashtags', value='\n#'.join(hashtags))
        em.set_thumbnail(url=champ.get_avatar())
        # em2 = discord.Embed(color=champ.class_color,
        # title=champ.full_name + ' Special Attacks')
        # em2.add_field(name=specials[0], value=specials[3])
        # em2.add_field(name=specials[1], value=specials[4])
        # em2.add_field(name=specials[2], value=specials[5])
        em.add_field(name='Shortcode', value=champ.short)
        em.set_footer(text='MCOC Game Files', icon_url='https://imgur.com/UniRf5f.png')
        await self.bot.say(embed=em)
        # await self.bot.say(embed=em2)

    # @commands.command()
    # async def sigarray(self, champ : ChampConverter, dbg=1, *args):
    #     '''Retrieve the Signature Ability of a Champion at multiple levels'''
    #     champ = self._resolve_alias(champ)
    #     title, desc = champ.get_sigarray(**self.settings)
    #     if dbg == 0:
    #         em = discord.Embed(color=champ.class_color, title=title,
    #                 description=desc)
    #     elif dbg == 1:
    #         em = discord.Embed(color=champ.class_color, title=champ.full_name)
    #         em.add_field(name='Signature Ability Array', value=desc)
    #     else:
    #         em = discord.Embed(color=champ.class_color, title=title)
    #         em.add_field(name='__SigLvl__', value='1\n20\n40')
    #         em.add_field(name='__X__', value='1.0\n1.9\n2.1', inline=True)
    #
    #     em.set_thumbnail(url=champ.get_avatar())
    #     await self.bot.say(embed=em)

    @champ.command(name='prestige')
    async def champ_prestige(self, *, champs : ChampConverterMult):
        '''Retrieve prestige data for champs'''
        #em = discord.Embed(color=discord.Color.magenta(), title='Prestige')
        pch = [c for c in champs if c.has_prestige]
        em = discord.Embed(color=discord.Color.magenta(), title='Prestige',
                description='\n'.join([c.verbose_prestige_str for c in
                    sorted(pch, key=attrgetter('prestige'), reverse=True)]))
        #for champ in sorted(pch, key=attrgetter('prestige'), reverse=True):
            #try:
            #em.add_field(name='{0.class_icon} {0.star_char}{0.star} {0.full_name}'.format(champ),
                    #value='{0.stars_str}\n{0.rank_sig_str}\n{0.prestige}'.format(champ),
            #        value='{0.rank_sig_str}\n{0.prestige}'.format(champ),
            #        inline=False)
            #except AttributeError:
            #    await self.bot.say("**WARNING** Champion Data for "
            #        + "{} does not exist".format(champ.verbose_str))
        ##em.set_thumbnail(url=champ.get_avatar())
        await self.bot.say(embed=em)

    @champ.command(name='aliases', aliases=('calias','ca'))
    async def champ_aliases(self, *args):
        '''Retrieve Champion Aliases'''
        em = discord.Embed(color=discord.Color.teal(), title='Champion Aliases')
        champs_matched = set()
        for arg in args:
            if (arg.startswith("'") and arg.endswith("'")) or \
                    (arg.startswith('"') and arg.endswith('"')):
                champs = await self.search_champions(arg[1:-1])
            elif '*' in arg:
                champs = await self.search_champions('.*'.join(re.split(r'\\?\*', arg)))
            else:
                champs = await self.search_champions('.*{}.*'.format(arg))
            for champ in champs:
                if champ.mattkraftid not in champs_matched:
                    em.add_field(name=champ.full_name, value=champ.get_aliases())
                    champs_matched.add(champ.mattkraftid)
        await self.bot.say(embed=em)

    @commands.command()
    async def phc(self):
        '''Premium Hero Crystal Release Dates'''
        await self.bot.upload(data_files['phc_jpg']['local'],
                content='Dates Champs are added to PHC (and as 5* Featured for 2nd time)')


    @commands.command(hidden=True)
    async def tst(self, key):
        files = {'bio': (kabam_bio, 'ID_CHARACTER_BIOS_', 'mcocjson'),
                 'sig': (kabam_bcg_stat_en, 'ID_UI_STAT_', 'mcocsig')}
        ignore_champs = ('DRONE', 'SYMBIOD')
        if key not in files:
            await self.bot.say('Accepted Key values:\n\t' + '\n\t'.join(files.keys()))
            return
        data = load_kabam_json(files[key][0])
        no_mcocjson = []
        no_kabam_key = []
        data_keys = {k for k in data.keys() if k.startswith(files[key][1])}
        ignore_keys = set()
        for champ in ignore_champs:
            ignore_keys.update({k for k in data_keys if k.find(champ) != -1})
        data_keys -= ignore_keys
        print(ignore_keys)
        for champ in self.champs:
            if not getattr(champ, files[key][2], None):
                no_mcocjson.append(champ.full_name)
                continue
            kabam_key = files[key][1] + getattr(champ, files[key][2])
            champ_keys = {k for k in data.keys() if k.startswith(kabam_key)}
            if not champ_keys:
                no_kabam_key.append(champ.full_name)
            else:
                data_keys -= champ_keys
        if no_mcocjson:
            await self.bot.say('Could not find mcocjson alias for champs:\n\t' + ', '.join(no_mcocjson))
        if no_kabam_key:
            await self.bot.say('Could not find Kabam key for champs:\n\t' + ', '.join(no_kabam_key))
        if data_keys:
            #print(data_keys, len(data_keys))
            if len(data_keys) > 20:
                dump = {k for k in data_keys if k.endswith('TITLE')}
            else:
                dump = data_keys
            await self.bot.say('Residual keys:\n\t' + '\n\t'.join(dump))
        await self.bot.say('Done')

#My intention was to create a hook command group. If nothing is specified, then drop the URL

    #def _prepare_signature_data(self):
        #raw_data = load_csv(local_files['sig_coeff'])

def validate_attr(*expected_args):
    def decorator(func):
        def wrapper(self, *args, **kwargs):
            for attr in expected_args:
                if getattr(self, attr + '_data', None) is None:
                    raise AttributeError("{} for Champion ".format(attr.capitalize())
                        + "'{}' has not been initialized.".format(self.champ))
            return func(self, *args, **kwargs)
        return wrapper
    return decorator


class Champion:

    base_tags = {'#cr{}'.format(i) for i in range(10, 130, 10)}
    base_tags.update({'#{}star'.format(i) for i in range(1, 6)})
    base_tags.update({'#awake', '#sig0'})
    dupe_levels = {2: 1, 3: 8, 4: 20, 5: 20}
    default_stars = {i: {'rank': i+1, 'sig': 99} for i in range(1,5)}
    default_stars[5] = {'rank': 3, 'sig': 200}

    def __init__(self, attrs=None):
        if attrs is None:
            attrs = {}
        self.debug = attrs.pop('debug', 0)

        self._star = attrs.pop('star', 4)
        if self._star < 1:
            logger.warn('Star {} for Champ {} is too low.  Setting to 1'.format(
                    self._star, self.full_name))
            self._star = 1
        if self._star > 5:
            logger.warn('Star {} for Champ {} is too high.  Setting to 5'.format(
                    self._star, self.full_name))
            self._star = 5
        self._default = self.default_stars[self._star].copy()

        for k,v in attrs.items():
            if k not in self._default:
                setattr(self, k, v)
        self.tags = set()
        self.update_attrs(attrs)

    def __eq__(self, other):
        return self.immutable_id == other.immutable_id \
                and self.rank == other.rank \
                and self.sig == other.sig

    def update_attrs(self, attrs):
        self.tags.difference_update(self.base_tags)
        for k in ('rank', 'sig'):
            if k in attrs:
                setattr(self, '_' + k, attrs[k])
        if self.sig < 0:
            self._sig = 0
        if self.rank < 1:
            self._rank = 1
        if self.star == 5:
            if self.rank > 5:
                self._rank = 5
            if self.sig > 200:
                self._sig = 200
        elif self.star < 5:
            if self.rank > (self.star + 1):
                self._rank = self.star + 1
            if self.sig > 99:
                self._sig = 99
        self.tags.add('#cr{}'.format(self.chlgr_rating))
        self.tags.add('#{}star'.format(self.star))
        if self.sig == 0:
            self.tags.add('#sig0')
        else:
            self.tags.add('#awake')

    def update_default(self, attrs):
        self._default.update(attrs)

    def inc_dupe(self):
        self.update_attrs({'sig': self.sig + self.dupe_levels[self.star]})

    def get_avatar(self):
        image = '{}portraits/portrait_{}.png'.format(remote_data_basepath, self.mcocportrait)
        logger.debug(image)
        return image

    def get_featured(self):
        image = '{}uigacha/featured/GachaChasePrize_256x256_{}.png'.format(
                    remote_data_basepath, self.mcocfeatured)
        logger.debug(image)
        return image

    async def get_bio(self):
        bios = load_kabam_json(kabam_bio)
        key = 'ID_CHARACTER_BIOS_' + self.mcocjson
        if self.debug:
            dbg_str = 'BIO:  ' + key
            await self.bot.say('```{}```'.format(dbg_str))
        if key not in bios:
            raise KeyError('Cannot find Champion {} in data files'.format(self.full_name))
        return bios[key]

    @property
    def star(self):
        return self._star

    @property
    def rank(self):
        return getattr(self, '_rank', self._default['rank'])

    @property
    def sig(self):
        return getattr(self, '_sig', self._default['sig'])

    def is_defined(self, attr):
        return hasattr(self, '_' + attr)

    @property
    def immutable_id(self):
        return (type(self), self.star)

    @property
    def duel_str(self):
        return '{0.star}{0.star_char} {0.rank}/{0.max_lvl} {0.full_name}'.format(self)

    @property
    def star_str(self):
        return '{0.stars_str} {0.rank}/{0.max_lvl}'.format(self)

    @property
    def attrs_str(self):
        return '{0.star}{0.star_char} {0.rank}/{0.max_lvl} sig{0.sig}'.format(self)

    @property
    def unique(self):
        return '{0.star}-{0.mattkraftid}-{0.rank}'.format(self)

    @property
    def coded_str(self):
        return '{0.star}*{0.short}r{0.rank}s{0.sig}'.format(self)

    @property
    def verbose_str(self):
        return '{0.stars_str} {0.full_name} r{0.rank}'.format(self)

    @property
    def star_name_str(self):
        return '{0.star}{0.star_char} {0.full_name}'.format(self)
        #return '{0.star}★ {0.full_name}'.format(self)

    @property
    def rank_sig_str(self):
        return '{0.rank}/{0.max_lvl} sig{0.sig:<2}'.format(self)

    @property
    def verbose_prestige_str(self):
        return ('{0.class_icon} {0.star}{0.star_char} {0.full_name} '
                + 'r{0.rank} s{0.sig:<2} [ {0.prestige} ]').format(self)

    @property
    def stars_str(self):
        return self.star_char * self.star

    @property
    def star_char(self):
        if self.sig:
            return '★'
        else:
            return '☆'

    @property
    def chlgr_rating(self):
        if self.star == 1:
            return self.rank * 10
        else:
            return (2 * self.star - 3 + self.rank) * 10

    @property
    def max_lvl(self):
        if self.star < 5:
            return self.rank * 10
        else:
            return 15 + self.rank * 10

    @property
    def all_tags(self):
        return self.tags.union(self.class_tags)

    def to_json(self):
        translate = {'sig': 'Awakened', 'hookid': 'Id', 'max_lvl': 'Level',
                    'prestige': 'Pi', 'rank': 'Rank', 'star': 'Stars',
                    'quest_role': 'Role', 'max_prestige': 'maxpi'}
        pack = {}
        for attr, hook_key in translate.items():
            pack[hook_key] = getattr(self, attr, '')
        return pack

    def get_special_attacks(self):
        specials = load_kabam_json(kabam_special_attacks)
        prefix = 'ID_SPECIAL_ATTACK_'
        desc = 'DESCRIPTION_'
        zero = '_0'
        one = '_1'
        two = '_2'
        s0 = specials[prefix + self.mcocjson + zero]
        s1 = specials[prefix + self.mcocjson + one]
        s2 = specials[prefix + self.mcocjson + two]
        s0d = specials[prefix + desc + self.mcocjson + zero]
        s1d = specials[prefix + desc + self.mcocjson + one]
        s2d = specials[prefix + desc + self.mcocjson + two]
        specials = (s0, s1, s2, s0d, s1d, s2d)
        return specials

    @property
    @validate_attr('prestige')
    def prestige(self):
        try:
            if self.prestige_data[self.star][self.rank-1] is None:
                return 0
        except KeyError:
            return 0
        return self.prestige_data[self.star][self.rank-1][self.sig]

    @property
    def has_prestige(self):
        return hasattr(self, 'prestige_data')

    @property
    @validate_attr('prestige')
    def max_prestige(self):
        cur_rank = self.rank
        if self.star == 5:
            rank = 3 if cur_rank < 4 else 4
        else:
            rank = self.star + 1
        self.update_attrs({'rank': rank})
        maxp = self.prestige
        self.update_attrs({'rank': cur_rank})
        return maxp

    @validate_attr('prestige')
    def get_prestige_arr(self, rank, sig_arr, star=4):
        row = ['{}r{}'.format(self.short, rank)]
        for sig in sig_arr:
            try:
                row.append(self.prestige_data[star][rank-1][sig])
            except:
                logger.error(rank, sig, self.prestige_data)
                raise
        return row

    async def missing_sig_ad(self):
        em = discord.Embed(color=self.class_color,
                title='Signature Data is Missing')
        em.add_field(name=self.full_name,
                value='Contribute your data at http://discord.gg/wJqpYGS')
        await self.bot.say(embed=em)

    async def process_sig_description(self, quiet=False):
        brkt_re = re.compile(r'{([0-9])}')
        sigs = load_kabam_json(kabam_bcg_stat_en)
        title, title_lower, simple, desc = self.get_mcoc_keys()
        if self.debug:
            dbg_str = ['Title:  ' + title]
            dbg_str.append('Simple:  ' + ', '.join(simple))
            dbg_str.append('Description Keys:  ')
            dbg_str.append('  ' + ', '.join(desc))
            dbg_str.append('Description Text:  ')
            dbg_str.extend(['  ' + self._sig_header(sigs[d]) for d in desc])
            await self.bot.say(chat.box('\n'.join(dbg_str)))

        coeff = self.get_sig_coeff()
        ekey = self.get_effect_keys()
        spotlight = self.get_spotlight()
        if coeff is None or ekey is None:
            raise KeyError("Missing Sig data for {}".format(self.full_name))
        else:
            logger.debug('coeff and ekey check out')

        if self.sig == 0:
            return sigs[title], '\n'.join([sigs[k] for k in simple]), None
        sig_calcs = {}
        ftypes = {}
        data_missing = False
        for i in map(str, range(6)):
            if not ekey['Location_' + i]:
                break
            effect = ekey['Effect_' + i]
            try:
                m = float(coeff['ability_norm' + i])
                b = float(coeff['offset' + i])
            except:
                if not quiet:
                    await self.missing_sig_ad()
                self.update_attrs({'sig': 0})
                return sigs[title], '\n'.join([sigs[k] for k in simple]), None
            ckey = ekey['Location_' + i]
            raw_str = '{:.2f}'
            raw_per_str = '{:.2%}'
            per_str = '{:.2f} ({:.2%})'

            if effect == 'rating':
                sig_calcs[ckey] = raw_str.format(m * self.chlgr_rating + b)
                continue
            per_val = m * log(self.sig) + b
            if effect == 'flat':
                sig_calcs[ckey] = per_str.format(
                        to_flat(per_val, self.chlgr_rating), per_val/100)
            elif effect == 'attack':
                if not spotlight['attack']:
                    data_missing = True
                    sig_calcs[ckey] = raw_per_str.format(per_val/100)
                    continue
                sig_calcs[ckey] = per_str.format(
                        int(spotlight['attack'].replace(',','')) * per_val / 100, per_val/100)
            elif effect == 'health':
                if not spotlight['health']:
                    data_missing = True
                    sig_calcs[ckey] = raw_per_str.format(per_val/100)
                    continue
                sig_calcs[ckey] = per_str.format(
                        int(spotlight['health'].replace(',','')) * per_val / 100, per_val/100)
            else:
                if per_val.is_integer():
                    sig_calcs[ckey] = '{:.0f}'.format(per_val)
                else:
                    sig_calcs[ckey] = raw_str.format(per_val)

        if data_missing:
            await self.bot.say(('Missing Attack/Health info for '
                    + '{0.full_name} {0.star_str}').format(self))
        fdesc = []
        for i, kabam_key in enumerate(desc):
            fdesc.append(brkt_re.sub(r'{{d[{0}-\1]}}'.format(i),
                        self._sig_header(sigs[kabam_key])))
        if self.debug:
            await self.bot.say(chat.box('\n'.join(fdesc)))
        return sigs[title], '\n'.join(fdesc), sig_calcs

    def get_mcoc_keys(self):
        sigs = load_kabam_json(kabam_bcg_stat_en)
        mcocsig = self.mcocsig
        preamble = None
        title = None
        title_lower = None
        simple = []
        desc = []

        if mcocsig == 'COMICULTRON':
            mcocsig = 'DRONE_TECH'
        elif mcocsig == 'CYCLOPS_90S':
            mcocsig = 'CYCLOPS'

        titles = ('ID_UI_STAT_SIGNATURE_{}_TITLE'.format(mcocsig),
            'ID_UI_STAT_ATTRIBUTE_{}_TITLE'.format(mcocsig),
            'ID_UI_STAT_{}_SIGNATURE_TITLE'.format(mcocsig),
            'ID_UI_STAT_SIG_{}_TITLE'.format(mcocsig),
            'ID_UI_STAT_ATTRIBUTE_{}_SIGNATURE_TITLE'.format(mcocsig),
            'ID_UI_STAT_ATTRIBUTE_{}_SIG_TITLE'.format(mcocsig),
            'ID_UI_STAT_SIGNATURE_FORMAT_{}_SIG_TITLE'.format(mcocsig),
            'ID_UI_STAT_SIGNATURE_{}_SIG_TITLE'.format(mcocsig),
            )

        for x in titles:
            if x in sigs:
                title = x

        if title is None:
            raise KeyError('DEBUG - title not found')
        elif title + '_LOWER' in sigs:
            title_lower = title + '_LOWER'

        if self.mcocsig == 'COMICULTRON':
            mcocsig = self.mcocsig  # re-init for Ultron Classic

        preambles = ('ID_UI_STAT_SIGNATURE_{}'.format(mcocsig),
            'ID_UI_STAT_{}_SIGNATURE'.format(mcocsig),
            'ID_UI_STAT_SIG_{}'.format(mcocsig),
            'ID_UI_STAT_ATTRIBUTE_{}_SIGNATURE'.format(mcocsig),
            'ID_UI_STAT_SIGNATURE_FORMAT_{}_SIG'.format(mcocsig),
            'ID_UI_STAT_SIGNATURE_{}_SIG'.format(mcocsig),
            )

        for x in preambles:
            if x + '_SIMPLE' in sigs:
                preamble = x
                break

        # if preamble is 'undefined':
        #     raise KeyError('DEBUG - Preamble not found')
        if preamble + '_SIMPLE_NEW2' in sigs:
            simple.append(preamble + '_SIMPLE_NEW2')
        if preamble + '_SIMPLE_NEW' in sigs:
            simple.append(preamble + '_SIMPLE_NEW')
        elif preamble + '_SIMPLE' in sigs:
            simple.append(preamble + '_SIMPLE')
        else:
            raise KeyError('Signature SIMPLE cannot be found with: {}_SIMPLE'.format(preamble))

        champ_exceptions = {
            #'CYCLOPS_90S': ['ID_UI_STAT_SIGNATURE_CYCLOPS_DESC_90S_AO'],
            'CYCLOPS_90S': ['ID_UI_STAT_SIGNATURE_CYCLOPS_DESC_90S_AO'],
            'LOKI': ['ID_UI_STAT_SIGNATURE_LOKI_LONGDESC'],
            'DEADPOOL': ['ID_UI_STAT_SIGNATURE_DEADPOOL_DESC2_AO'],
            #'ULTRON': ['ID_UI_STAT_SIGNATURE_ULTRON_DESC'],
            #'COMICULTRON': ['ID_UI_STAT_SIGNATURE_ULTRON_DESC'],
            'IRONMAN_SUPERIOR': ['ID_UI_STAT_SIGNATURE_IRONMAN_DESC_AO',
                    'ID_UI_STAT_SIGNATURE_IRONMAN_DESC_B_AO'],
            'BEAST': ['ID_UI_STAT_SIGNATURE_LONGDESC_AO',
                    'ID_UI_STAT_SIGNATURE_LONGDESC_B_AO',
                    'ID_UI_STAT_SIGNATURE_LONGDESC_C_AO',
                    'ID_UI_STAT_SIGNATURE_LONGDESC_D_AO',
                    'ID_UI_STAT_SIGNATURE_LONGDESC_E_AO'],
            'GUILLOTINE': ['ID_UI_STAT_SIGNATURE_GUILLOTINE_DESC'],
            'NEBULA': ['ID_UI_STAT_SIGNATURE_NEBULA_LONG'],
            'RONAN': ['ID_UI_STAT_SIGNATURE_RONAN_DESC_AO'],
            'MORDO': ['ID_UI_STAT_SIG_MORDO_DESC_AO'],
        }

        if self.mcocsig == 'CYCLOPS_90S':
            desc.append('ID_UI_STAT_SIGNATURE_CYCLOPS_DESC_90S_AO')
        elif mcocsig in champ_exceptions:
            desc.extend(champ_exceptions[mcocsig])
        elif preamble + '_DESC_NEW' in sigs:
            desclist = ('_DESC_NEW','_DESC_NEW_B')
            if preamble + '_DESC_NEW2' in sigs:
                desclist = ('_DESC_NEW2','_DESC_NEW2_B')
            for k in desclist:
                if preamble + k in sigs:
                    if preamble + k + '_AO' in sigs:
                        desc.append(preamble + k + '_AO')
                    else:
                        desc.append(preamble + k)
        elif preamble + '_5STAR_DESC_MOD' in sigs:
            desc.append(preamble+'_DESC_MOD')
        else:
            for k in ('_DESC','_DESC_A','_DESC_B'):
                if preamble + k + '_UPDATED' in sigs:
                    k = k + '_UPDATED'
                if preamble + k in sigs:
                    if preamble + k + '_ALT' in sigs:
                        desc.append(preamble + k + '_ALT')
                    elif preamble + k + '_AO' in sigs:
                        desc.append(preamble + k + '_AO')
                    else:
                        desc.append(preamble + k)

        #print(desc)
        return title, title_lower, simple, desc

    def get_sig_coeff(self):
        return get_csv_row(local_files['sig_coeff'], 'CHAMP', self.full_name)

    def get_effect_keys(self):
        return get_csv_row(local_files['effect_keys'], 'CHAMP', self.full_name)

    def get_spotlight(self, default=None):
        return get_csv_row(data_files['spotlight']['local'], 'unique',
                self.unique, default=default)

    def get_aliases(self):
        return '```{}```'.format(', '.join(self.alias_set))

    @staticmethod
    def _sig_header(str_data):
        hex_re = re.compile(r'\[[0-9a-f]{6,8}\](.+?)\[-\]', re.I)
        return '• ' + hex_re.sub(r'**\1**', str_data)

def bound_lvl(siglvl, max_lvl=99):
    if isinstance(siglvl, list):
        ret = []
        for j in siglvl:
            if j > max_lvl:
                j = max_lvl
            elif j < 0:
                j = 0
            ret.append(j)
    else:
        ret = siglvl
        if siglvl > max_lvl:
            ret = max_lvl
        elif siglvl < 0:
            ret = 0
    return ret

def tabulate(table_data, width, rotate=True, header_sep=True, align_out=True):
    rows = []
    cells_in_row = None
    for i in iter_rows(table_data, rotate):
        if cells_in_row is None:
            cells_in_row = len(i)
        elif cells_in_row != len(i):
            raise IndexError("Array is not uniform")
        if align_out:
            fstr = '{:<{width}}'
            if len(i) > 1:
                fstr += '|' + '|'.join(['{:>{width}}']*(len(i)-1))
            rows.append(fstr.format(*i, width=width))
        else:
            rows.append('|'.join(['{:^{width}}']*len(i)).format(*i, width=width))
    if header_sep:
        rows.insert(1, '|'.join(['-' * width] * cells_in_row))
    return chat.box('\n'.join(rows))

def iter_rows(array, rotate):
    if not rotate:
        for i in array:
            yield i
    else:
        for j in range(len(array[0])):
            row = []
            for i in range(len(array)):
                row.append(array[i][j])
            yield row

def load_kabam_json(file):
    raw_data = dataIO.load_json(file)
    data = {}
    for d in raw_data['strings']:
        data[d['k']] = d['v']
    return data

def _truncate_text(self, text, max_length):
    if len(text) > max_length:
        if text.strip('$').isdigit():
            text = int(text.strip('$'))
            return "${:.2E}".format(text)
        return text[:max_length-3] + "..."
    return text

def get_csv_row(filecsv, column, match_val, default=None):
    logger.debug(match_val)
    csvfile = load_csv(filecsv)
    for row in csvfile:
        if row[column] == match_val:
            if default is not None:
                for k, v in row.items():
                    if v == '':
                        row[k] = default
            return row

def get_csv_rows(filecsv, column, match_val, default=None):
    logger.debug(match_val)
    csvfile = load_csv(filecsv)
    package =[]
    for row in csvfile:
        if row[column] == match_val:
            if default is not None:
                for k, v in row.items():
                    if v == '':
                        row[k] = default
            package.append(row)
    return package

def load_csv(filename):
    return csv.DictReader(open(filename))

def padd_it(word,max : int,opt='back'):
    loop = max-len(str(word))
    if loop > 0:
        padd = ''
        for i in loop:
            padd+=' '
        if opt =='back':
            return word+padd
        else:
            return padd+word
    else:
        logger.warn('Padding would be negative.')


# Creation of lookup functions from a tuple through anonymous functions
#for fname, docstr, link in MCOC.lookup_functions:
    #async def new_func(self):
        #await self.bot.say('{}\n{}'.format(docstr, link))
        #raise Exception
    ##print(new_func)
    ##setattr(MCOC, fname, commands.command(name=fname, help=docstr)(new_func))
    #new_func = commands.command(name=fname, help=docstr)(new_func)
    #setattr(MCOC, fname, new_func)
    ##print(getattr(MCOC, fname).name, getattr(MCOC, fname).callback)



def setup(bot):
    if not hasattr(bot, '_command_error_orig'):
        bot._command_error_orig = bot.on_command_error
        @bot.event
        async def on_command_error(error, ctx):
            if isinstance(error, QuietUserError):
                bot.logger.info('<{}> {}'.format(type(error).__name__, error))
            else:
                await bot._command_error_orig(error, ctx)
    bot.add_cog(MCOC(bot))
