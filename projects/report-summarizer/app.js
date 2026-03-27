(function () {
  var loadingLine = document.getElementById('loadingLine');
  var loadErr = document.getElementById('loadErr');
  var loadErrMsg = document.getElementById('loadErrMsg');
  var app = document.getElementById('app');

  function showError(err) {
    loadingLine.hidden = true;
    loadErr.hidden = false;
    loadErrMsg.textContent = ' ' + (err && err.message ? err.message : String(err));
  }

  fetch('fixtures/reports.json')
    .then(function (res) {
      if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
      return res.json();
    })
    .then(function (data) {
      if (!data || !Array.isArray(data.reports) || data.reports.length === 0) {
        throw new Error('Invalid or empty report data.');
      }

      loadingLine.hidden = true;
      app.hidden = false;

      var disclaimerEl = document.getElementById('dataDisclaimer');
      disclaimerEl.textContent = data.disclaimer || '';

      var select = document.getElementById('reportSelect');
      data.reports.forEach(function (r, i) {
        var opt = document.createElement('option');
        opt.value = String(i);
        var label = r.title || r.id || 'Report ' + (i + 1);
        if (r.modality) label += ' · ' + r.modality;
        opt.textContent = label;
        select.appendChild(opt);
      });

      var rawEl = document.getElementById('rawReport');
      var impressionEl = document.getElementById('impressionSummary');
      var keyUl = document.getElementById('keyFindings');
      var followEl = document.getElementById('followUpRecommendations');
      var patientEl = document.getElementById('patientSummary');

      function render(index) {
        var r = data.reports[index];
        var s = r.summaries || {};
        rawEl.textContent = r.rawReport || '';
        impressionEl.textContent = s.impressionSummary || '—';
        followEl.textContent = s.followUpRecommendations || '—';
        patientEl.textContent = s.patientSummary || '—';
        keyUl.innerHTML = '';
        var items = Array.isArray(s.keyFindings) ? s.keyFindings : [];
        if (items.length === 0) {
          var empty = document.createElement('li');
          empty.textContent = '—';
          keyUl.appendChild(empty);
        } else {
          items.forEach(function (line) {
            var li = document.createElement('li');
            li.textContent = line;
            keyUl.appendChild(li);
          });
        }
      }

      select.addEventListener('change', function () {
        render(parseInt(select.value, 10));
      });
      render(0);
    })
    .catch(showError);
})();
