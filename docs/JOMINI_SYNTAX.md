OK, in that case let's talk about jomini script a little bit so you can finish.
jomini script, in the most simplest of examples, can look like toml:
```jomini
# this is a comment
a = 1
b = "hello" # inline comment
# comment block start
# comment block end
```
However, jomini is also quite "loose" and contain many edge cases
```jomini
a = 1
b = "hello"
a = 2
```
In the above example, `a` would go from mapping a singular value to becoming a list. This is absolutely valid jomini syntax, but could prove to be a little difficult for us.

Let's look at the most common scalars:
```jomini
aaa=foo         # a plain scalar
bbb=-1          # an integer scalar
ccc=1.000       # a decimal scalar
ddd=yes         # a true scalar
eee=no          # a false scalar
fff="foo"       # a quoted scalar
ggg=1821.1.1    # a date scalar in Y.M.D format
```
Some notes:

A quoted scalar can contain any of other scalar (date, integers, boolean)
A quoted scalar can contain any character including newlines. Everything until the next unescaped quote is valid
A quoted scalar can contain non-ascii characters like "Jåhkåmåhkke". The encoding for quoted scalars will be either Windows-1252 (games like EU4) or UTF-8 (games like CK3)
Decimal scalars vary in precision between games and context. Sometimes precision is recorded to thousandths, tens-thousandths, etc.
Numbers can be fit into one of the following: 32 bit signed integers, 64 bit unsigned integers, or 32 bit floating point.
Numbers can have a leading plus sign that should be ignored.
Dates do not incorporate leap years, so don't try sticking it in your language's date representation.
One should delay assigning a type to a scalar as it may be ambiguous if yes should be treated as a string or a boolean. This is more of a problem for the binary format as dates are encoded as integers so eagerly assigning a type could mean that the client sees dates when they expected integers.

Keys are scalars:
```jomini
-1=aaa
"1821.1.1"=bbb
@my_var="ccc"    # define a variable
```

One can have multiple key values pairs per line as long as boundary character is separating them:
```jomini
a=1 b=2 c=3
```

Whitespace is considered a boundary, but we'll see more.

Quoted scalars are by far the trickiest as they have several escape rules:
```jomini
hhh="a\"b"      # escaped quote. Equivalent to `a"b`
iii="\\"        # escaped escape. Equivalent to `\`
mmm="\\\""      # multiple escapes. Equivalent to `\"`

# a multiline quoted scalar
ooo="hello
     world"

# Quotes can contain escape codes! Imperator uses them as
# color codes (somehow `0x15` is translated to `#` in the
# parsing process)
nnn="ab <0x15>D ( ID: 691 )<0x15>!"
```
I think we were wrong here regarding escapes as well. In our _lex_string() in our lexer (lines 259-281), we are checking to see if strings are "closed" and raising a diagnostic error, we might need to change this?

Arrays and objects are values that contain either multiple values or multiple key-value pairs.

Below, flags is an object.
```jomini
flags={
    schools_initiated=1444.11.11
    mol_polish_march=1444.12.4
}
```
And an array looks quite similar:
```jomini
players_countries={
    "Player"
    "ENG"
}
```
And one can have arrays of objects
```jomini
campaign_stats={ {
    id=0
    comparison=1
    key="game_country"
    selector="ENG"
    localization="England"
} {
    id=1
    comparison=2
    key="longest_reign"
    localization="Henry VI"
} }
```
Operators
There are more operators than equality separating keys from values:
```
intrigue >= high_skill_rating
age > 16
count < 2
scope:attacker.primary_title.tier <= tier_county
a != b
start_date == 1066.9.15
c:RUS ?= this
```
These operators are typically reserved for game files (save files only use equals).

Boundary Characters
Mentioned earlier, what separates values are boundary characters. Boundary characters are:

Whitespace
Open ({) and close (}) braces
An operator
Quotes
Comments
Thus, one can make some pretty condensed documents.
```jomini
a={b="1"c=d}foo=bar#good
```
Which is equivalent to:
```jomini
a = {
  b = "1"
  c = d
}
foo = bar # good
```


Comments can occur at any location and cause the rest of the line to be ignored. The one exception is when the comment occurs inside a quote -- treat it as a regular character (we already have this):
```
my_obj = # this is going to be great
{ # my_key = prev_value
    my_key = value # better_value
    a = "not # a comment"
} # the end
```

Now we get into the weeds and see more edge cases.

An object / array value does not need to be prefixed with an operator:
```jomini
foo{bar=qux}
```
is equivalent to `foo={bar=qux}`

A value of {} could mean an empty array or empty object depending on the context. I like to leave it up to the caller to decide.
```jomini
discovered_by={} 
```
Any number of empty objects / arrays can occur in an object and should be skipped.
```jomini
history={{} {} 1629.11.10={core=AAA}}
```

An object can be both an array and an object at the same time:
```jomini
brittany_area = { #5
    color = { 118  99  151 }
    169 170 171 172 4384
}
```
The previous example showed how an object transitions to an array as seen in EU4 game files. In CK3 there is the opposite occurrence as shown below: an array transitions to an object. I colloquially refer to these as array trailers (EU4) and hidden objects (CK3):
```jomini
levels={ 10 0=2 1=2 }
# I view it as equivalent to
# levels={ { 10 } { 0=2 1=2 } }
```
Scalars can have non-alphanumeric characters:
```jomini
flavor_tur.8=yes
dashed-identifier=yes
province_id = event_target:agenda_province
@planet_standard_scale = 11
```
Variables can be used in interpolated expressions:
```jomini
position_x = @[1-leo_x]
```
Don't try to blank store all numbers as 64 bit floating point, as there are some 64 bit unsigned integers that would cause floating point to lose precision:
```jomini
identity=18446744073709547616
# converted to floating point would equal:
# identity=18446744073709548000
```
Equivalent quoted and unquoted scalars are not always intepretted the same by EU4, so one should preserve if a value was quoted in whatever internal structure. It is unknown if other games suffer from this phenomenon. The most well known example is how EU4 will only accept the quoted values for a field:
```jomini
unit_type="western"  # bad: save corruption
unit_type=western    # good
```
Victoria II has instances where unquoted keys contain non-ascii characters (specifically Windows-1252 which matches the Victoria II save file encoding).
```jomini
jean_jaurès = { }
```
A scalar has at least one character:
```jomini
# `=` is the key and `bar` is the value
=="bar"
```
Unless the empty string is quoted:
```jomini
name=""
```
Some of these edge cases are pretty niche, for example occuring only in EU4 save files. I think we could ignore something like `=="bar"` for now. However, we must be sure to remember it, so note it down as a potential future edge case in a new docs/EDGE_CASES_FAILURE.md file.

The type of an object or array can be externally tagged:
```
color = rgb { 100 200 150 }
color = hsv { 0.43 0.86 0.61 }
color = hsv360{ 25 75 63 }
color = hex { aabbccdd }
mild_winter = LIST { 3700 3701 }
```
The EU4 1.26 (Dharma) patch introduced parameter syntax that hasn't been seen in other PDS titles. From the changelog:

Syntax is [[var_name] code here ] for if variable is defined or [[!var_name] code here ] for if it is not.

An example of the parameter syntax:
```jomini
generate_advisor = {
  [[scaled_skill]
    $scaled_skill$
  ]
  [[!skill] if = {} ]
}
```
Objects can be infinitely nested. I've seen modded EU4 saves contain recursive events that reach several hundred deep.
```jomini
a={b={c={a={b={c=1}}}}}
```
The first line of save files indicate the format of the save and shouldn't be considered part of the standard syntax.
```jomini
EU4txt
date=1444.12.4
```
It is valid for a file to have extraneous closing braces, which can be seen in Victoria II saves, CK2 saves, and EU4 game files (looking at you verona.txt):
```jomini
a = { 1 }
}
b = 2
```
And at the opposite end, it is valid for files to have a missing bracket:
```jomini
a = { b=c
```
The previous three examples are specific to save files from older games, and newer games have toned weird shit like this down by a lot. As such, instead of allowing things extraneous brackets, let's note down these edge cases in our edge cases failure file and instead fail/emit diagnostics on these.

Semi-colons at the end of quotes (potentially lines) are ignored.
```jomini
textureFile3 = "gfx//mapitems//trade_terrain.dds";
```
The Deep End
This section contains examples that contradict other examples. Due to the nature of Clausewitz being closed source, libraries can never guarantee compatibility with Clausewitz. From what we do know, Clausewitz is recklessly flexible: allowing each game object to potentially define its own unique syntax. The good news is that this fringe syntax is typically isolated in a handful of game files.

There are unmarked lists in CK3 and Imperator. Typically lists are use brackets ({, }) but those are conspicuously missing here:
```jomini
simple_cross_flag = {
  pattern = list "christian_emblems_list"
  color1 = list "normal_colors"
}
```
Alternating value and key value pairs. Makes one wish they used a bit more of a self describing format:
```jomini
on_actions = {
  faith_holy_order_land_acquisition_pulse
  delay = { days = { 5 10 }}
  faith_heresy_events_pulse
  delay = { days = { 15 20 }}
  faith_fervor_events_pulse
}
```
In direct constrast to the example above, some values need to be skipped like the first definition shown below.
```jomini
pride_of_the_fleet = yes
definition
definition = heavy_cruiser
```
I don't expect any parser to be able to handle all these edge cases in an ergonomic and performant manner. As such, we can just note these down in edge cases failure file. 

