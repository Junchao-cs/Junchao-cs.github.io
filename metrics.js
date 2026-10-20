(function () {
  'use strict';

  var metricLabels = {
    'solarrenderer-github-metric': 'GitHub stars',
    'solarrenderer-huggingface-metric': 'Hugging Face downloads (weights + data)',
    'solarwm-github-metric': 'GitHub stars',
    'solarwm-huggingface-metric': 'Hugging Face downloads',
    'solarwm-modelscope-metric': 'ModelScope downloads'
  };

  function humanize(value) {
    if (value >= 1000000) {
      return (value / 1000000).toFixed(1).replace(/\.0$/, '') + 'M';
    }
    if (value >= 1000) {
      return (value / 1000).toFixed(1).replace(/\.0$/, '') + 'k';
    }
    return String(value);
  }

  function updateMetric(id, value) {
    if (!Number.isSafeInteger(value) || value < 0) {
      return;
    }

    var metric = document.getElementById(id);
    var valueElement = metric && metric.querySelector('.paper-metric-value');
    if (!metric || !valueElement) {
      return;
    }

    var exactValue = value.toLocaleString('en-US') + ' ' + metricLabels[id];
    valueElement.textContent = humanize(value);
    metric.setAttribute('aria-label', exactValue);
    metric.title = exactValue;
    metric.hidden = false;
  }

  async function fetchJson(url) {
    var response = await fetch(url, { cache: 'no-store' });
    if (!response.ok) {
      throw new Error('Metric request failed: ' + response.status);
    }
    return response.json();
  }

  async function fetchGitHubStars(repositoryId) {
    try {
      var repository = await fetchJson('https://api.github.com/repos/' + repositoryId);
      if (Number.isSafeInteger(repository.stargazers_count)) {
        return repository.stargazers_count;
      }
    } catch (error) {
      // Fall through to Shields when GitHub's anonymous API quota is exhausted.
    }

    var shield = await fetchJson('https://img.shields.io/github/stars/' + repositoryId + '.json');
    var compactValue = String(shield.value || shield.message || '').trim();
    var match = compactValue.match(/^([\d.]+)([kKmM]?)$/);
    if (!match) {
      throw new Error('GitHub star count is missing.');
    }

    var multiplier = match[2].toLowerCase() === 'm' ? 1000000 :
      match[2].toLowerCase() === 'k' ? 1000 : 1;
    return Math.round(Number(match[1]) * multiplier);
  }

  async function fetchHuggingFaceRepositoryDownloads(type, repositoryId) {
    var encodedId = repositoryId.split('/').map(encodeURIComponent).join('/');
    var repository = await fetchJson(
      'https://huggingface.co/api/' + type + '/' + encodedId + '?expand=downloadsAllTime'
    );
    if (!Number.isSafeInteger(repository.downloadsAllTime) || repository.downloadsAllTime < 0) {
      throw new Error('Hugging Face download count is missing.');
    }
    return repository.downloadsAllTime;
  }

  async function fetchSolarRendererHuggingFaceDownloads() {
    var repositories = [
      ['models', 'Enderfga/SolarRenderer'],
      ['datasets', 'Enderfga/SolarRenderer-Data']
    ];
    var downloads = await Promise.all(repositories.map(function (item) {
      return fetchHuggingFaceRepositoryDownloads(item[0], item[1]);
    }));
    return downloads.reduce(function (total, value) {
      return total + value;
    }, 0);
  }

  async function fetchSolarWMHuggingFaceDownloads() {
    var collection = await fetchJson('https://huggingface.co/api/collections/junchaoh-cs/solarwm');
    var repositories = (collection.items || []).filter(function (item) {
      return (item.type === 'model' || item.type === 'dataset') && item.id;
    });

    var uniqueRepositories = Array.from(new Map(repositories.map(function (item) {
      return [item.type + ':' + item.id, item];
    })).values());

    if (!uniqueRepositories.length) {
      throw new Error('The Hugging Face collection is empty.');
    }

    var downloads = await Promise.all(uniqueRepositories.map(async function (item) {
      var type = item.type === 'dataset' ? 'datasets' : 'models';
      return fetchHuggingFaceRepositoryDownloads(type, item.id);
    }));

    return downloads.reduce(function (total, value) {
      return total + value;
    }, 0);
  }

  async function fetchModelScopeDownloads() {
    var sources = [
      'https://modelscope.cn/api/v1/datasets?Owner=junchao2003&PageNumber=1&PageSize=100',
      'https://modelscope.ai/api/v1/datasets?Owner=Junchao-cs&PageNumber=1&PageSize=100'
    ];

    var responses = await Promise.all(sources.map(fetchJson));
    var repositories = responses.flatMap(function (response) {
      if (response.Code !== 200 || !Array.isArray(response.Data)) {
        throw new Error('ModelScope dataset list is unavailable.');
      }
      return response.Data;
    }).filter(function (repository) {
      return /^SolarWM(?:-|_)/i.test(repository.Name || '');
    });

    if (!repositories.length) {
      throw new Error('No SolarWM datasets were found on ModelScope.');
    }

    return repositories.reduce(function (total, repository) {
      if (!Number.isSafeInteger(repository.Downloads) || repository.Downloads < 0) {
        throw new Error('ModelScope download count is missing.');
      }
      return total + repository.Downloads;
    }, 0);
  }

  [
    ['solarrenderer-github-metric', function () { return fetchGitHubStars('Enderfga/SolarRenderer'); }],
    ['solarrenderer-huggingface-metric', fetchSolarRendererHuggingFaceDownloads],
    ['solarwm-github-metric', function () { return fetchGitHubStars('Junchao-cs/SolarWM'); }],
    ['solarwm-huggingface-metric', fetchSolarWMHuggingFaceDownloads],
    ['solarwm-modelscope-metric', fetchModelScopeDownloads]
  ].forEach(function (entry) {
    entry[1]().then(function (value) {
      updateMetric(entry[0], value);
    }).catch(function () {
      // Leave this metric hidden if its public API is unavailable.
    });
  });
})();
