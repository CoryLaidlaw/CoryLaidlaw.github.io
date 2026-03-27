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

  function asPercent(value) {
    var num = Number(value);
    if (!Number.isFinite(num)) return '—';
    return Math.round(num * 100) + '%';
  }

  function fillList(el, items, emptyText) {
    el.innerHTML = '';
    if (!Array.isArray(items) || items.length === 0) {
      var empty = document.createElement('li');
      empty.textContent = emptyText || '—';
      el.appendChild(empty);
      return;
    }
    items.forEach(function (item) {
      var li = document.createElement('li');
      if (typeof item === 'string') {
        li.textContent = item;
      } else {
        var label = item.finding || item.text || 'Finding';
        var conf = Number(item.confidence);
        var evidence = item.evidence ? ' — ' + item.evidence : '';
        li.textContent = label + (Number.isFinite(conf) ? ' (' + asPercent(conf) + ')' : '') + evidence;
      }
      el.appendChild(li);
    });
  }

  fetch('fixtures/study-analysis.json')
    .then(function (res) {
      if (!res.ok) throw new Error(res.status + ' ' + res.statusText);
      return res.json();
    })
    .then(function (data) {
      if (!data || !data.analysis || !Array.isArray(data.analysis.series_analysis)) {
        throw new Error('Invalid study-analysis.json structure.');
      }

      loadingLine.hidden = true;
      app.hidden = false;

      document.getElementById('disclaimer').textContent = data.disclaimer || '';
      document.getElementById('studyId').textContent = data.study_id || data.analysis.study_id || '—';
      document.getElementById('seriesCount').textContent = String(data.series_count || data.analysis.series_count || '—');
      var shownSlices = data.selected_slice_count;
      var analysisSlices = data.analysis_slice_count;
      if (typeof shownSlices === 'number' && typeof analysisSlices === 'number') {
        document.getElementById('sliceCount').textContent = String(shownSlices) + ' shown / ' + String(analysisSlices) + ' analyzed';
      } else {
        document.getElementById('sliceCount').textContent = String(data.selected_slice_count || '—');
      }
      document.getElementById('generatedAt').textContent = data.generated_at || '—';

      document.getElementById('studyVisual').textContent = data.analysis.study_visual_description || '—';
      document.getElementById('safetyNote').textContent = data.analysis.safety_note || '';
      fillList(document.getElementById('studyFindings'), data.analysis.possible_findings, 'No possible findings reported.');
      fillList(document.getElementById('studyUncertainties'), data.analysis.uncertainties, 'No explicit uncertainties reported.');

      var selected = Array.isArray(data.selected_slices) ? data.selected_slices : [];
      var bySeries = {};
      selected.forEach(function (slice) {
        var sid = slice.series_id || 'unknown-series';
        if (!bySeries[sid]) bySeries[sid] = [];
        bySeries[sid].push(slice);
      });

      var metaBySeries = {};
      if (Array.isArray(data.series_metadata)) {
        data.series_metadata.forEach(function (m) {
          if (m && m.series_id) metaBySeries[m.series_id] = m;
        });
      }

      var cardsHost = document.getElementById('seriesCards');
      cardsHost.innerHTML = '';

      data.analysis.series_analysis.forEach(function (series) {
        var card = document.createElement('article');
        card.className = 'series-card';

        var head = document.createElement('div');
        head.className = 'series-head';
        var title = document.createElement('div');
        title.className = 'series-title';
        title.textContent = (series.series_id || 'Series') + ' · ' + (series.likely_series_type || 'Unknown type');
        var conf = document.createElement('div');
        conf.className = 'series-confidence';
        conf.textContent = 'Confidence ' + asPercent(series.series_type_confidence);
        head.appendChild(title);
        head.appendChild(conf);
        card.appendChild(head);

        var meta = metaBySeries[series.series_id] || {};
        var metaLine = document.createElement('p');
        metaLine.className = 'meta';
        var bits = [];
        if (meta.modality) bits.push('Modality: ' + meta.modality);
        if (meta.series_description) bits.push('Description: ' + meta.series_description);
        if (meta.instance_count) bits.push('Instances: ' + meta.instance_count);
        metaLine.textContent = bits.join(' · ') || 'Metadata available in JSON.';
        card.appendChild(metaLine);

        var rationale = document.createElement('p');
        rationale.textContent = series.rationale || '—';
        card.appendChild(rationale);

        var visual = document.createElement('p');
        visual.textContent = series.visual_description || '—';
        card.appendChild(visual);

        var findingsHeader = document.createElement('h3');
        findingsHeader.textContent = 'Possible findings';
        card.appendChild(findingsHeader);
        var findings = document.createElement('ul');
        fillList(findings, series.possible_findings, 'No possible findings reported.');
        card.appendChild(findings);

        var uncHeader = document.createElement('h3');
        uncHeader.textContent = 'Uncertainties';
        card.appendChild(uncHeader);
        var unc = document.createElement('ul');
        fillList(unc, series.uncertainties, 'No explicit uncertainties reported.');
        card.appendChild(unc);

        var conciseHeader = document.createElement('h3');
        conciseHeader.textContent = 'Concise summary';
        card.appendChild(conciseHeader);
        var concise = document.createElement('p');
        concise.textContent = series.concise_summary || 'No concise summary generated yet.';
        card.appendChild(concise);

        var thumbs = document.createElement('div');
        thumbs.className = 'thumbs';
        (bySeries[series.series_id] || []).forEach(function (slice) {
          var fig = document.createElement('figure');
          var img = document.createElement('img');
          img.src = slice.image_path;
          img.alt = (series.series_id || 'Series') + ' ' + (slice.slice_label || 'slice');
          var cap = document.createElement('figcaption');
          cap.textContent = (slice.slice_label || 'slice') + (slice.instance_number ? ' · #' + slice.instance_number : '');
          fig.appendChild(img);
          fig.appendChild(cap);
          thumbs.appendChild(fig);
        });
        if (thumbs.children.length > 0) {
          card.appendChild(thumbs);
        }

        cardsHost.appendChild(card);
      });
    })
    .catch(showError);
})();
