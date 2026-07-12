
export const sweetHome = (function() {
  const href = document.location.href;
  const urlObj = new URL(href);
  const is_dev = urlObj.port === "3000";

  return {
    href,
    urlObj,
    getQueryStringValue: (key) => {
      let value = ((urlObj && urlObj.search) && urlObj.searchParams.get(key)) || null;
      return value;
    },
    baseUrl: urlObj.protocol + '//' + urlObj.hostname + ':' + urlObj.port,
    // For deployment, backendUrl is same as baseUrl. Just a hack for now

    backendUrl: is_dev ?
      'http://localhost:8312' : urlObj.protocol + '//' + urlObj.hostname + ':' + urlObj.port,

    websocketUrl: is_dev ?
      'ws://localhost:8312' : urlObj.protocol + '//' + urlObj.hostname + ':' + urlObj.port,
  };
})();

// then, to grab the base URL anytime you need it: sweetHome.baseUrl
// and grab the value of an arbitrary query parameter: sweetHome.getQueryStringValue('partner_key');
