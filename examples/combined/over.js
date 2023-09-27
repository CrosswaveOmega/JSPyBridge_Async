
async function overevent(myObject,countUntil,otherObj) {
    myObject['world'] = 'hello';
    console.log(myObject)
    for (let x = 0; x < countUntil; x++) {// s
        await otherObj.append(x)
        await otherObj.myArray.append('A')
    }
    return 'it worked';
}

module.exports = {overevent};