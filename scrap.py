import json

list = ['route1', 'route2', 'route3']

with open('testList.json', 'w') as file:
    json.dump(list, file)


loadedList = ['route0']
try:
    with open('testLists.json', 'r') as file:
        loadedList += json.load(file)
except Exception as e:
    print(e)

print(loadedList)