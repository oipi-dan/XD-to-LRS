import sys



if __name__ == '__main__':
    args = sys.argv
    print('args:')
    for arg in args[1:]:
        print(f'    {arg}')