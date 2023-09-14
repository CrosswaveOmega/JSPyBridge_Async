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

async function read_webpage_plain(targeturl, readability, jsdom, turndownService) {
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
  
    turndownService.addRule('removeInvalidLinks', {
      filter: 'a',
      replacement: (content, node) => {
        const href = node.getAttribute('href');
        if (!href || !isValidLink(href)) {
          return content;
        }
        return href ? `[${content}](${href})` : content;
      }
    });
  
    const markdownContent = turndownService.turndown(articleHtml);
    return [markdownContent, article.title];
  }

  async function read_webpage_html_direct(htmldoc,targeturl, readability, jsdom,turndownService) {
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
    
    const html2 = htmldoc
    var doc = new jsdom.JSDOM(html2, {
      url: targeturl
    });
    let reader = new readability.Readability(doc.window.document);
    let article = reader.parse();
    let articleHtml = article.content;
    //The heading style recognized by discord apps.
    turndownService.addRule('removeInvalidLinks', {
      filter: 'a',
      replacement: (content, node) => {
        const href = node.getAttribute('href');
        if (!href || !isValidLink(href)) {
          return content;
        }
        return href ? `[${content}](${href})` : content;
      }
    });
  
    const markdownContent = turndownService.turndown(articleHtml);
    return [markdownContent, article.title];
}

module.exports = {
    check_read,
    read_webpage_plain,
    read_webpage_html_direct
}