import sys
import argparse
import json


def process_command_line(argv):
    '''Parse the command line and do a first-pass on processing them into a
    format appropriate for the rest of the script.'''

    parser = argparse.ArgumentParser(formatter_class=argparse.
                                     ArgumentDefaultsHelpFormatter)

    parser.add_argument("json",
                        help="The JSON file to read.")
    parser.add_argument('--keys',
                        help="The keys to extract.")

    args = parser.parse_args(argv[1:])

    import re

    # this could easily be accomplished by two split operations...
    keyop_list = re.split(r'(\||&)', args.keys)

    keysets = [{keyop_list[0]}]
    for (op, key) in zip(keyop_list[1::2],  # pylint: disable=C0103
                         keyop_list[2::2]):
        if op == '|':
            keysets[-1].add(key)
        elif op == '&':
            keysets.append({key})
        else:
            assert False

    args.keys = keysets
    print args.keys

    return args


def findkey(keys, subdict):
    '''Build the subdictionary containing only keys in 'keys' as leaves.'''

    filtdict = {}

    for i in subdict:

        # if the value is in keys, add it
        try:
            if subdict[i] in keys:
                filtdict[i] = subdict[i]
        except TypeError:
            pass

        if i in keys:
            # print "leaf i"
            filtdict[i] = subdict[i]
        elif isinstance(subdict[i], dict):
            lower = findkey(keys, subdict[i])

            if lower is not None:
                filtdict[i] = lower
        elif isinstance(subdict[i], dict):
            filtdict[i] = [findkey(keys, v) for v in subdict[i]]

    return filtdict if len(filtdict) > 0 else None


def main(argv=None):
    '''Run the driver script for this module. This code only runs if we're
    being run as a script. Otherwise, it's silent and just exposes methods.'''
    args = process_command_line(argv)

    with open(args.json, 'r') as f:
        in_dict = json.loads(f.read())

    for keylist in args.keys:
        in_dict = findkey(keylist, in_dict)

    print json.dumps(in_dict, sort_keys=True,
                     indent=2, separators=(',', ': '))

    return 1

if __name__ == "__main__":
    sys.exit(main(sys.argv))
