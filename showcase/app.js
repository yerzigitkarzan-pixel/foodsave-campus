/* Standalone teaching examples. No API, accounts, persistence, or network requests. */
(function (root) {
  'use strict';
  const reasons = Object.freeze({
    preparation: 'Тазалау және дайындау',
    overproduction: 'Артық дайындау',
    spoilage: 'Бүліну немесе мерзімінің өтуі',
    plate_leftovers: 'Тамақтан кейінгі қалдық',
    other: 'Басқа себеп',
    unspecified: 'Белгіленбеген'
  });
  class InputError extends Error {}
  function numeric(raw, label, max, places) {
    const text = String(raw ?? '').trim().replace(',', '.');
    if (text === '') throw new InputError(label + ': сан енгізіңіз.');
    const pattern = places === 0 ? /^\d+$/ : new RegExp('^(?:\\d+(?:\\.\\d{0,' + places + '})?|\\.\\d{1,' + places + '})$');
    if (!pattern.test(text)) throw new InputError(label + ': 0 немесе одан үлкен ' + (places === 0 ? 'бүтін сан' : 'сан') + ' енгізіңіз.');
    const value = Number(text);
    if (!Number.isFinite(value) || value > max) throw new InputError(label + ': ең үлкен мән — ' + max + '.');
    return value;
  }
  function measurement(values) {
    const mass = numeric(values.mass, 'Қалдық салмағы', 10000, 3);
    const reason = Object.hasOwn(reasons, values.reason) ? values.reason : 'unspecified';
    if (String(values.portions ?? '').trim() === '') return {mass, reason, portions: null, value: null, state: 'unknown'};
    const portions = numeric(values.portions, 'Порциялар саны', 100000, 0);
    return {mass, reason, portions, value: portions > 0 ? mass / portions * 100 : null, state: portions > 0 ? 'calculated' : 'zero'};
  }
  function economy(values) {
    const extraPortions = numeric(values.extraPortions, 'Артық порциялар', 10000, 0);
    const portionCost = numeric(values.portionCost, 'Бір порцияның құны', 1000000, 2);
    const workDays = numeric(values.workDays, 'Жұмыс күні', 366, 0);
    return {extraPortions, portionCost, workDays, value: extraPortions * portionCost * workDays};
  }
  function ecology(values) {
    const mass = numeric(values.mass, 'Қалдық салмағы', 10000, 3);
    if (String(values.landfillFactor ?? '').trim() === '' || String(values.compostFactor ?? '').trim() === '') {
      return {mass, value: null, state: 'unknown'};
    }
    const landfillFactor = numeric(values.landfillFactor, 'Полигон коэффициенті', 1000000, 5);
    const compostFactor = numeric(values.compostFactor, 'Компосттау коэффициенті', 1000000, 5);
    const tonnes = mass / 1000;
    const landfill = tonnes * landfillFactor;
    const compost = tonnes * compostFactor;
    return {mass, tonnes, landfillFactor, compostFactor, landfill, compost, value: landfill - compost, state: 'calculated'};
  }
  const calculations = Object.freeze({numeric, measurement, economy, ecology, reasons, InputError});
  if (typeof module === 'object' && module.exports) module.exports = calculations;
  root.FoodSaveShowcase = calculations;
  if (!root.document) return;

  const document = root.document;
  const number = (value, places = 3) => {
    const tiny = value !== 0 && Math.abs(value) < Math.pow(10, -places);
    return new Intl.NumberFormat('kk-KZ', {maximumFractionDigits: tiny ? 12 : places}).format(value);
  };
  const set = (id, value) => { document.getElementById(id).textContent = value; };
  const values = form => Object.fromEntries(new root.FormData(form));
  function renderMeasurement() {
    const form = document.getElementById('measurement-form');
    try {
      const result = measurement(values(form));
      set('measurement-error', '');
      set('measurement-reason', 'Себеп: ' + reasons[result.reason] + '.');
      if (result.value === null) {
        set('measurement-result', '—');
        set('measurement-formula', result.state === 'unknown' ? 'Порциялар саны белгісіз.' : '0 порция: бұл күні порция берілмеген.');
        set('measurement-status', result.state === 'unknown' ? 'Есептеу үшін порциялар санын енгізіңіз.' : '100 порцияға шаққандағы көрсеткіш есептелмейді.');
        return;
      }
      set('measurement-result', number(result.value, 6));
      set('measurement-formula', number(result.mass) + ' кг ÷ ' + number(result.portions, 0) + ' × 100 = ' + number(result.value, 6) + ' кг');
      set('measurement-status', 'Бірдей порция санына шаққанда күндерді салыстыруға болады.');
    } catch (error) {
      set('measurement-result', '—');
      set('measurement-formula', 'Есептеу үшін өрістерді тексеріңіз.');
      set('measurement-status', '');
      set('measurement-error', error.message);
    }
  }
  function renderEconomy() {
    try {
      const result = economy(values(document.getElementById('economy-form')));
      set('economy-error', '');
      set('economy-result', number(result.value, 2));
      set('economy-formula', number(result.extraPortions, 0) + ' × ' + number(result.portionCost, 2) + ' ₸ × ' + number(result.workDays, 0) + ' = ' + number(result.value, 2) + ' ₸');
    } catch (error) {
      set('economy-result', '—');
      set('economy-formula', 'Есептеу үшін үш санды да енгізіңіз.');
      set('economy-error', error.message);
    }
  }
  function renderEcology() {
    try {
      const result = ecology(values(document.getElementById('ecology-form')));
      set('ecology-error', '');
      if (result.value === null) {
        set('ecology-result', '—');
        set('ecology-conversion', number(result.mass) + ' кг ÷ 1 000 = ' + number(result.mass / 1000, 6) + ' т');
        set('landfill-result', 'Коэффициенттерді енгізіңіз.');
        set('compost-result', 'Коэффициенттерді енгізіңіз.');
        set('ecology-formula', 'Коэффициент белгісіз.');
        set('ecology-status', 'Есептеу үшін екі коэффициентті де енгізіңіз.');
        return;
      }
      set('ecology-result', number(result.value, 6));
      set('ecology-conversion', number(result.mass) + ' кг ÷ 1 000 = ' + number(result.tonnes, 6) + ' т');
      set('landfill-result', number(result.tonnes, 6) + ' × ' + number(result.landfillFactor, 5) + ' = ' + number(result.landfill, 6) + ' кг CO₂-баламасы');
      set('compost-result', number(result.tonnes, 6) + ' × ' + number(result.compostFactor, 5) + ' = ' + number(result.compost, 6) + ' кг CO₂-баламасы');
      set('ecology-formula', number(result.landfill, 6) + ' − ' + number(result.compost, 6) + ' = ' + number(result.value, 6) + ' кг CO₂-баламасы');
      set('ecology-status', result.value > 0 ? 'Компосттаудың есептік шығарындылары төмен.' : result.value < 0 ? 'Таңдалған тәсілдің есептік шығарындылары жоғары.' : 'Екі тәсілдің есептік нәтижесі бірдей.');
    } catch (error) {
      set('ecology-result', '—');
      set('ecology-conversion', 'Есептеу үшін өрістерді тексеріңіз.');
      set('landfill-result', '—');
      set('compost-result', '—');
      set('ecology-formula', '');
      set('ecology-status', '');
      set('ecology-error', error.message);
    }
  }
  const panels = [['measurement-form', renderMeasurement], ['economy-form', renderEconomy], ['ecology-form', renderEcology]];
  for (const [id, render] of panels) {
    const form = document.getElementById(id);
    form.addEventListener('input', render);
    form.addEventListener('change', render);
    form.addEventListener('submit', event => { event.preventDefault(); render(); });
    form.addEventListener('reset', () => root.setTimeout(render, 0));
    render();
  }
})(typeof window === 'object' ? window : globalThis);
