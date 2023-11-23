async function check_read(targeturl, readability, jsdom) {
  if (typeof readability === 'undefined') {
    readability = require('@mozilla/readability');
  }

  if (typeof jsdom === 'undefined') {
    jsdom = require('jsdom');
  }

  var red = readability;
  var ji = jsdom;

  function isValidLink(url) {
    // Regular expression pattern to validate URL format
    const urlPattern = /^(ftp|http|https):\/\/[^ "]+$/;

    return urlPattern.test(url);
  }

  const response = await fetch(targeturl);
  const html2 = await response.text();
  var doc = new jsdom.JSDOM(html2, {
    url: targeturl
  });
  return readability.isProbablyReaderable(doc.window.document)
}

async function read_webpage_plain(targeturl, readability, jsdom) {
    if (typeof readability === 'undefined') {
      readability = require('@mozilla/readability');
    }
  
    if (typeof jsdom === 'undefined') {
      jsdom = require('jsdom');
    }
  
    var red = readability;
    var ji = jsdom;
  
    function isValidLink(url) {
      // Regular expression pattern to validate URL format
      const urlPattern = /^(ftp|http|https):\/\/[^ "]+$/;
  
      return urlPattern.test(url);
    }
  
    const response = await fetch(targeturl);
    const html2 = await response.text();
    var doc = new jsdom.JSDOM(html2, {
      url: targeturl
    });
    let reader = new readability.Readability(doc.window.document);
    let article = reader.parse();
    let articleHtml = article.content;
  
 
    return [articleHtml, article];
  }


module.exports = {
    check_read,
    read_webpage_plain
}