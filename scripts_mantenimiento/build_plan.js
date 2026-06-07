const {
  Document, Packer, Paragraph, TextRun, Table, TableRow, TableCell,
  HeadingLevel, AlignmentType, BorderStyle, WidthType, ShadingType,
  VerticalAlign, PageNumber, PageBreak, LevelFormat, Header, Footer,
  TabStopType, TabStopPosition
} = require('docx');
const fs = require('fs');

const COLORS = {
  black:      '1A1A1A',
  darkBlue:   '0D1B2A',
  blue:       '1B4F8A',
  lightBlue:  'D6E4F0',
  green:      '1A6B3C',
  lightGreen: 'D4EFDF',
  red:        '922B21',
  lightRed:   'FADBD8',
  amber:      '7D6608',
  lightAmber: 'FEF9E7',
  gray:       '5D6D7E',
  lightGray:  'F2F3F4',
  white:      'FFFFFF',
  accent:     '2874A6',
};

const border = { style: BorderStyle.SINGLE, size: 1, color: 'CCCCCC' };
const borders = { top: border, bottom: border, left: border, right: border };
const noBorder = { style: BorderStyle.NONE, size: 0, color: 'FFFFFF' };
const noBorders = { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder };

function p(text, opts = {}) {
  return new Paragraph({
    spacing: { before: opts.spaceBefore ?? 80, after: opts.spaceAfter ?? 80 },
    alignment: opts.align ?? AlignmentType.LEFT,
    children: [new TextRun({
      text,
      bold: opts.bold ?? false,
      italics: opts.italic ?? false,
      size: opts.size ?? 22,
      color: opts.color ?? COLORS.black,
      font: 'Arial',
    })]
  });
}

function h1(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_1,
    spacing: { before: 320, after: 160 },
    border: { bottom: { style: BorderStyle.SINGLE, size: 8, color: COLORS.blue, space: 4 } },
    children: [new TextRun({ text, bold: true, size: 36, color: COLORS.darkBlue, font: 'Arial' })]
  });
}

function h2(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_2,
    spacing: { before: 240, after: 120 },
    children: [new TextRun({ text, bold: true, size: 28, color: COLORS.blue, font: 'Arial' })]
  });
}

function h3(text) {
  return new Paragraph({
    heading: HeadingLevel.HEADING_3,
    spacing: { before: 180, after: 80 },
    children: [new TextRun({ text, bold: true, size: 24, color: COLORS.accent, font: 'Arial' })]
  });
}

function bullet(text, level = 0) {
  return new Paragraph({
    numbering: { reference: 'bullets', level },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text, size: 22, font: 'Arial', color: COLORS.black })]
  });
}

function numbered(text, level = 0) {
  return new Paragraph({
    numbering: { reference: 'numbers', level },
    spacing: { before: 40, after: 40 },
    children: [new TextRun({ text, size: 22, font: 'Arial', color: COLORS.black })]
  });
}

function code(text) {
  return new Paragraph({
    spacing: { before: 60, after: 60 },
    indent: { left: 720 },
    children: [new TextRun({
      text,
      font: 'Courier New',
      size: 18,
      color: COLORS.darkBlue,
    })]
  });
}

function spacer(lines = 1) {
  return new Paragraph({ spacing: { before: 40 * lines, after: 40 * lines }, children: [new TextRun('')] });
}

function alertBox(label, text, bgColor, borderColor) {
  return new Table({
    width: { size: 9360, type: WidthType.DXA },
    columnWidths: [9360],
    rows: [
      new TableRow({
        children: [new TableCell({
          borders: {
            top: { style: BorderStyle.SINGLE, size: 4, color: borderColor },
            bottom: { style: BorderStyle.SINGLE, size: 4, color: borderColor },
            left: { style: BorderStyle.THICK, size: 12, color: borderColor },
            right: { style: BorderStyle.SINGLE, size: 4, color: borderColor },
          },
          shading: { fill: bgColor, type: ShadingType.CLEAR },
          margins: { top: 120, bottom: 120, left: 200, right: 120 },
          width: { size: 9360, type: WidthType.DXA },
          children: [
            new Paragraph({
              spacing: { before: 0, after: 60 },
              children: [new TextRun({ text: label, bold: true, size: 20, color: borderColor, font: 'Arial' })]
            }),
            new Paragraph({
              spacing: { before: 0, after: 0 },
              children: [new TextRun({ text, size: 20, color: COLORS.black, font: 'Arial' })]
            })
          ]
        })]
      })
    ]
  });
}

function twoColRow(col1, col2, bg1 = COLORS.lightGray, bg2 = COLORS.white) {
  return new TableRow({
    children: [
      new TableCell({
        borders,
        shading: { fill: bg1, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        width: { size: 3120, type: WidthType.DXA },
        children: [new Paragraph({ children: [new TextRun({ text: col1, bold: true, size: 20, font: 'Arial', color: COLORS.black })] })]
      }),
      new TableCell({
        borders,
        shading: { fill: bg2, type: ShadingType.CLEAR },
        margins: { top: 80, bottom: 80, left: 120, right: 120 },
        width: { size: 6240, type: WidthType.DXA },
        children: [new Paragraph({ children: [new TextRun({ text: col2, size: 20, font: 'Arial', color: COLORS.black })] })]
      })
    ]
  });
}

function threeColRow(c1, c2, c3, header = false) {
  const bg = header ? COLORS.darkBlue : COLORS.white;
  const fg = header ? COLORS.white : COLORS.black;
  const bold = header;
  return new TableRow({
    tableHeader: header,
    children: [c1, c2, c3].map((text, i) => new TableCell({
      borders,
      shading: { fill: bg, type: ShadingType.CLEAR },
      margins: { top: 80, bottom: 80, left: 120, right: 120 },
      width: { size: [2400, 4560, 2400][i], type: WidthType.DXA },
      children: [new Paragraph({ children: [new TextRun({ text, bold, size: 20, font: 'Arial', color: fg })] })]
    }))
  });
}

function pageBreak() {
  return new Paragraph({ children: [new PageBreak()] });
}

// ─── DOCUMENT ─────────────────────────────────────────────────────────────────

const doc = new Document({
  numbering: {
    config: [
      {
        reference: 'bullets',
        levels: [{
          level: 0, format: LevelFormat.BULLET, text: '\u2022',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } }
        }, {
          level: 1, format: LevelFormat.BULLET, text: '\u25E6',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 1080, hanging: 360 } } }
        }]
      },
      {
        reference: 'numbers',
        levels: [{
          level: 0, format: LevelFormat.DECIMAL, text: '%1.',
          alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 720, hanging: 360 } } }
        }]
      }
    ]
  },
  styles: {
    default: {
      document: { run: { font: 'Arial', size: 22 } }
    },
    paragraphStyles: [
      {
        id: 'Heading1', name: 'Heading 1', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 36, bold: true, font: 'Arial', color: COLORS.darkBlue },
        paragraph: { spacing: { before: 320, after: 160 }, outlineLevel: 0 }
      },
      {
        id: 'Heading2', name: 'Heading 2', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 28, bold: true, font: 'Arial', color: COLORS.blue },
        paragraph: { spacing: { before: 240, after: 120 }, outlineLevel: 1 }
      },
      {
        id: 'Heading3', name: 'Heading 3', basedOn: 'Normal', next: 'Normal', quickFormat: true,
        run: { size: 24, bold: true, font: 'Arial', color: COLORS.accent },
        paragraph: { spacing: { before: 180, after: 80 }, outlineLevel: 2 }
      }
    ]
  },
  sections: [{
    properties: {
      page: {
        size: { width: 12240, height: 15840 },
        margin: { top: 1440, right: 1260, bottom: 1440, left: 1260 }
      }
    },
    headers: {
      default: new Header({
        children: [
          new Paragraph({
            border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: COLORS.blue, space: 4 } },
            tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
            children: [
              new TextRun({ text: 'PLAN MAESTRO DE IMPLEMENTACIÓN · SISTEMA DE TRADING S&P 500', size: 16, color: COLORS.gray, font: 'Arial' }),
              new TextRun({ text: '\t', font: 'Arial' }),
              new TextRun({ text: 'Para uso exclusivo de Antigravity', size: 16, color: COLORS.gray, font: 'Arial', italics: true }),
            ]
          })
        ]
      })
    },
    footers: {
      default: new Footer({
        children: [
          new Paragraph({
            border: { top: { style: BorderStyle.SINGLE, size: 4, color: COLORS.lightGray, space: 4 } },
            tabStops: [{ type: TabStopType.RIGHT, position: TabStopPosition.MAX }],
            alignment: AlignmentType.LEFT,
            children: [
              new TextRun({ text: 'CONFIDENCIAL · Sistema Open-to-Close · S&P 500 · v4.0', size: 16, color: COLORS.gray, font: 'Arial' }),
              new TextRun({ text: '\t', font: 'Arial' }),
              new TextRun({ children: [new PageNumber()], size: 16, color: COLORS.gray, font: 'Arial' }),
            ]
          })
        ]
      })
    },
    children: [

      // ══════════════════════════════════════════════════════
      // PORTADA
      // ══════════════════════════════════════════════════════
      new Paragraph({
        spacing: { before: 1800, after: 120 },
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: 'PLAN MAESTRO DE IMPLEMENTACIÓN', bold: true, size: 52, color: COLORS.darkBlue, font: 'Arial' })]
      }),
      new Paragraph({
        spacing: { before: 0, after: 80 },
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: 'Sistema de Trading Open-to-Close · S&P 500', size: 36, color: COLORS.blue, font: 'Arial' })]
      }),
      new Paragraph({
        spacing: { before: 0, after: 400 },
        alignment: AlignmentType.CENTER,
        children: [new TextRun({ text: 'Versión 4.0 · Para implementación directa por Antigravity', size: 24, color: COLORS.gray, font: 'Arial', italics: true })]
      }),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [4680, 4680],
        rows: [
          new TableRow({ children: [
            new TableCell({
              borders, shading: { fill: COLORS.lightBlue, type: ShadingType.CLEAR },
              margins: { top: 120, bottom: 120, left: 200, right: 200 },
              width: { size: 4680, type: WidthType.DXA },
              children: [
                new Paragraph({ children: [new TextRun({ text: 'OBJETIVO PRIMARIO', bold: true, size: 18, color: COLORS.blue, font: 'Arial' })] }),
                new Paragraph({ children: [new TextRun({ text: 'Sharpe > 1.5 | Max DD < 15%', size: 22, bold: true, font: 'Arial', color: COLORS.darkBlue })] }),
                new Paragraph({ children: [new TextRun({ text: 'Alpha > 5% vs SPY buy-and-hold', size: 18, font: 'Arial', color: COLORS.black })] }),
              ]
            }),
            new TableCell({
              borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR },
              margins: { top: 120, bottom: 120, left: 200, right: 200 },
              width: { size: 4680, type: WidthType.DXA },
              children: [
                new Paragraph({ children: [new TextRun({ text: 'ESTILO DE OPERACIÓN', bold: true, size: 18, color: COLORS.green, font: 'Arial' })] }),
                new Paragraph({ children: [new TextRun({ text: 'Open-to-Close exclusivo', size: 22, bold: true, font: 'Arial', color: COLORS.darkBlue })] }),
                new Paragraph({ children: [new TextRun({ text: 'Entrada 9:30am ET · Salida antes de 3:50pm ET', size: 18, font: 'Arial', color: COLORS.black })] }),
              ]
            })
          ]})
        ]
      }),

      spacer(2),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3120, 3120, 3120],
        rows: [
          new TableRow({ children: [
            new TableCell({
              borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR },
              margins: { top: 100, bottom: 100, left: 160, right: 160 },
              width: { size: 3120, type: WidthType.DXA },
              children: [
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'UNIVERSO', bold: true, size: 18, color: COLORS.gray, font: 'Arial' })] }),
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'S&P 500', bold: true, size: 26, color: COLORS.darkBlue, font: 'Arial' })] }),
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Sin ETFs ni opciones', size: 18, color: COLORS.gray, font: 'Arial' })] }),
              ]
            }),
            new TableCell({
              borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR },
              margins: { top: 100, bottom: 100, left: 160, right: 160 },
              width: { size: 3120, type: WidthType.DXA },
              children: [
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'PLATAFORMA', bold: true, size: 18, color: COLORS.gray, font: 'Arial' })] }),
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Streamlit', bold: true, size: 26, color: COLORS.darkBlue, font: 'Arial' })] }),
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'app.py + data_fetcher.py', size: 18, color: COLORS.gray, font: 'Arial' })] }),
              ]
            }),
            new TableCell({
              borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR },
              margins: { top: 100, bottom: 100, left: 160, right: 160 },
              width: { size: 3120, type: WidthType.DXA },
              children: [
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'PERSISTENCIA', bold: true, size: 18, color: COLORS.gray, font: 'Arial' })] }),
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Supabase', bold: true, size: 26, color: COLORS.darkBlue, font: 'Arial' })] }),
                new Paragraph({ alignment: AlignmentType.CENTER, children: [new TextRun({ text: 'Free tier · P&L + historial', size: 18, color: COLORS.gray, font: 'Arial' })] }),
              ]
            }),
          ]})
        ]
      }),

      spacer(4),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 0: CONTEXTO PARA ANTIGRAVITY
      // ══════════════════════════════════════════════════════
      h1('0. CONTEXTO PARA ANTIGRAVITY — LEER ANTES DE TOCAR CÓDIGO'),
      spacer(),

      alertBox(
        '⚠ CRÍTICO: Qué es este sistema',
        'Este es un sistema de trading algorítmico open-to-close sobre el S&P 500. Cada día de mercado: (1) genera señales pre-market entre 8:00-9:15am ET, (2) entra al open 9:30am ET, (3) gestiona stops y exits durante la sesión, (4) cierra TODO antes de 3:50pm ET. CERO posiciones overnight. Cada nivel de este documento es una mejora que debes implementar en orden estricto.',
        COLORS.lightAmber, COLORS.amber
      ),
      spacer(2),

      h2('0.1 Arquitectura actual vs arquitectura objetivo'),
      spacer(),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 3480, 3480],
        rows: [
          threeColRow('Componente', 'Estado actual (ROTO)', 'Estado objetivo', true),
          threeColRow('data_fetcher.py', 'Genera datos SINTÉTICOS cuando Yahoo falla. Corrompe señales.', 'Cascada real: Yahoo → yfinance → Polygon. Si todo falla: signal=False.'),
          threeColRow('Cache (lru_cache)', 'Se pierde en cada reinicio de Streamlit.', '@st.cache_data con TTL diferenciado por tipo de dato.'),
          threeColRow('Exits / stops', 'NUNCA cierra posiciones. 2 trades en 14 años (A.csv Agilent).', 'ATR(5) stop + trailing + take profit escalonado + hard close 3:50pm.'),
          threeColRow('Monte Carlo', 'Distribución Gaussiana. Subestima fat tails 6x.', 'Bootstrap con reemplazo sobre retornos históricos reales.'),
          threeColRow('Diagnóstico', 'Siempre muestra ✅ sin verificar nada (p_real = p_mem).', 'Diagnóstico real: latencia API, datos RAW, evaluate_signal() completo.'),
          threeColRow('Pre-market', 'No existe.', 'Nuevo módulo: gap%, vol relativo, sector momentum, catalizadores.'),
          threeColRow('Régimen de mercado', 'No existe.', '5 regímenes con VIX como árbitro absoluto.'),
          threeColRow('Sizing', 'Fijo o inexistente.', 'Half-Kelly rolling con multiplicadores por régimen y convicción.'),
          threeColRow('Paper trading DB', 'No existe.', 'Supabase: tabla trades + tabla signals_rejected.'),
        ]
      }),

      spacer(2),

      h2('0.2 Regla de oro para Antigravity'),
      spacer(),
      alertBox(
        '📌 NUNCA implementes en orden distinto al especificado',
        'El Nivel 0 (bug fixes) es prerrequisito de todo lo demás. Sin corregir el proxy sintético y los exits, cualquier mejora de los niveles superiores produce señales falsas o trades que nunca cierran. El orden de implementación de la Sección 11 es ESTRICTO.',
        COLORS.lightRed, COLORS.red
      ),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 1: BUGS CRÍTICOS
      // ══════════════════════════════════════════════════════
      h1('1. NIVEL 0 — BUG FIXES CRÍTICOS (Implementar primero)'),
      spacer(),
      p('Estos bugs hacen que el sistema no funcione. Sin corregirlos, todo lo demás es cosmético.', { bold: true, color: COLORS.red }),
      spacer(),

      h2('BUG 0.1 · Eliminar el Proxy Sintético'),
      h3('Archivo: data_fetcher.py'),
      spacer(),
      p('Problema: Cuando Yahoo Finance falla, el sistema genera datos sintéticos basados en momentum. Esto corrompe señales exactamente en los mercados más volátiles — el peor momento posible.'),
      spacer(),
      p('Solución exacta — reemplazar el bloque de fallback por:', { bold: true }),
      spacer(),
      code('import requests'),
      code('from urllib3.util.retry import Retry'),
      code('from requests.adapters import HTTPAdapter'),
      spacer(),
      code('def build_resilient_session():'),
      code('    session = requests.Session()'),
      code('    retry = Retry('),
      code('        total=3,'),
      code('        backoff_factor=1.5,'),
      code('        status_forcelist=[429, 500, 502, 503, 504]'),
      code('    )'),
      code('    adapter = HTTPAdapter(max_retries=retry)'),
      code('    session.mount("https://", adapter)'),
      code('    session.headers.update({"User-Agent": "Mozilla/5.0 (compatible; research)"})'),
      code('    return session'),
      spacer(),
      code('def fetch_data_cascade(ticker):'),
      code('    # Proveedor 1: Yahoo Finance directo'),
      code('    try: return fetch_yahoo_direct(ticker)'),
      code('    except: pass'),
      code('    # Proveedor 2: yfinance nativo'),
      code('    try: return fetch_yfinance_native(ticker)'),
      code('    except: pass'),
      code('    # Proveedor 3: Polygon.io free tier'),
      code('    try: return fetch_polygon_free(ticker)'),
      code('    except: pass'),
      code('    # Si los tres fallan: señal False. NUNCA datos sintéticos.'),
      code('    return None  # signal = False aguas arriba'),
      spacer(2),

      h2('BUG 0.2 · Reparar el Cache'),
      h3('Archivos: app.py + data_fetcher.py'),
      spacer(),
      p('Problema: lru_cache funciona por proceso Python, se limpia del módulo incorrecto, y se pierde en cada reinicio de Streamlit.'),
      spacer(),
      p('Solución — reemplazar TODO lru_cache con @st.cache_data con TTL diferenciado:', { bold: true }),
      spacer(),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3600, 2880, 2880],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Tipo de dato', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'TTL', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Razón', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Fundamentales', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'ttl=86400 (24h)', size: 20, font: 'Courier New', color: COLORS.accent })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'No cambian intradía', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Precios históricos', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'ttl=3600 (1h)', size: 20, font: 'Courier New', color: COLORS.accent })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Actualizan cada hora', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Indicadores técnicos', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'ttl=900 (15min)', size: 20, font: 'Courier New', color: COLORS.accent })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Balance precisión/costo API', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Datos pre-market', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'ttl=300 (5min)', size: 20, font: 'Courier New', color: COLORS.accent })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Máxima frescura pre-market', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Historial trades / P&L', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Supabase (permanente)', size: 20, font: 'Courier New', color: COLORS.green })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Persiste entre sesiones', size: 20, font: 'Arial' })] })] }),
          ]}),
        ]
      }),

      spacer(2),

      h2('BUG 0.3 · Reparar Monte Carlo'),
      h3('Archivo: lab/monte_carlo.py'),
      spacer(),
      p('Problema: Usa distribución Gaussiana. Los mercados tienen fat tails — eventos de -5% en un día ocurren 6x más frecuente de lo que la distribución normal predice.'),
      spacer(),
      p('Solución: Bootstrap con reemplazo sobre retornos históricos reales:', { bold: true }),
      spacer(),
      code('def monte_carlo_bootstrap(ticker, n_simulations=10000):'),
      code('    retornos_reales = obtener_retornos_historicos(ticker, dias=252)'),
      code('    if len(retornos_reales) < 60:'),
      code('        retornos_reales = obtener_retornos_historicos("SPY", dias=252)'),
      code('        nota = "ADVERTENCIA: datos insuficientes, usando SPY como proxy"'),
      code('    resultados = []'),
      code('    for _ in range(n_simulations):'),
      code('        # Bootstrap: samplear CON reemplazo (preserva fat tails reales)'),
      code('        retorno_dia = np.random.choice(retornos_reales, replace=True)'),
      code('        resultados.append(retorno_dia)'),
      code('    return {'),
      code('        "P_positivo":    np.mean(np.array(resultados) > 0),'),
      code('        "P_mayor_05":    np.mean(np.array(resultados) > 0.005),'),
      code('        "P_mayor_1":     np.mean(np.array(resultados) > 0.01),'),
      code('        "P_mayor_2":     np.mean(np.array(resultados) > 0.02),'),
      code('        "p10": np.percentile(resultados, 10),'),
      code('        "p50": np.percentile(resultados, 50),'),
      code('        "p90": np.percentile(resultados, 90),'),
      code('    }'),
      spacer(2),

      h2('BUG 0.4 · Reparar el Diagnóstico Placebo'),
      h3('Archivo: app.py líneas 1500-1502'),
      spacer(),
      p('Problema: p_real = p_mem, diff = 0, coincide = True — siempre muestra ✅ sin verificar nada.'),
      spacer(),
      p('Solución — diagnóstico real:', { bold: true }),
      spacer(),
      code('def run_real_diagnostic(ticker):'),
      code('    t0 = time.time()'),
      code('    raw_data = fetch_data_cascade(ticker)  # Datos reales, no memoria'),
      code('    latency_ms = (time.time() - t0) * 1000'),
      code('    fundamentals_raw = get_fundamentals_raw(ticker)'),
      code('    stars_calculated = calculate_stars(fundamentals_raw)'),
      code('    signal_result = evaluate_signal(ticker, raw_data, fundamentals_raw)'),
      code('    return {'),
      code('        "api_status": "OK" if raw_data else "FAILED",'),
      code('        "latency_ms": round(latency_ms, 1),'),
      code('        "price_live": raw_data["price"] if raw_data else None,'),
      code('        "fundamentals_raw": fundamentals_raw,'),
      code('        "stars": stars_calculated,'),
      code('        "signal_full": signal_result,  # Todos los campos'),
      code('    }'),
      spacer(2),

      h2('BUG 0.5 · Reparar la Lógica de Exits'),
      spacer(),
      p('Problema: El sistema nunca cierra posiciones. 2 trades en 14 años (visto en A.csv de Agilent). Capital bloqueado indefinidamente.'),
      spacer(),
      p('Ver Sección 3 (Sistema de Exits) para la implementación completa.', { italic: true, color: COLORS.accent }),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 2: SUPABASE SETUP
      // ══════════════════════════════════════════════════════
      h1('2. SUPABASE — Setup Completo (Semana 1)'),
      spacer(),
      p('Crear dos tablas en Supabase free tier. Ejecutar el siguiente SQL en el editor de Supabase:'),
      spacer(),

      h2('2.1 Tabla de Trades Ejecutados'),
      spacer(),
      code('CREATE TABLE trades ('),
      code('    id              SERIAL PRIMARY KEY,'),
      code('    fecha           DATE NOT NULL,'),
      code('    ticker          VARCHAR(10) NOT NULL,'),
      code('    signal          VARCHAR(5) NOT NULL,      -- LONG / SHORT'),
      code('    precio_entrada  FLOAT NOT NULL,'),
      code('    precio_salida   FLOAT,'),
      code('    return_pct      FLOAT,'),
      code('    exit_reason     VARCHAR(20),              -- stop_loss | trailing | take_profit_1 | take_profit_2 | hard_close'),
      code('    regime          VARCHAR(20),              -- BULL_FUERTE | BULL_DEBIL | LATERAL | BEAR_SUAVE | BEAR_FUERTE'),
      code('    confidence_stars FLOAT,'),
      code('    atr_5           FLOAT,'),
      code('    stop_loss_price FLOAT,'),
      code('    slippage_usado  FLOAT,'),
      code('    es_paper_trading BOOLEAN DEFAULT TRUE,'),
      code('    created_at      TIMESTAMP DEFAULT NOW()'),
      code(');'),
      spacer(2),

      h2('2.2 Tabla de Señales Rechazadas (tan importante como los trades)'),
      spacer(),
      alertBox(
        '💡 Por qué guardar señales rechazadas',
        'Si una señal rechazada por min_stars hubiera ganado 2%, eso es evidencia de que el umbral está demasiado alto. Este dataset es el más valioso para calibración continua del sistema.',
        COLORS.lightBlue, COLORS.accent
      ),
      spacer(),
      code('CREATE TABLE signals_rejected ('),
      code('    id              SERIAL PRIMARY KEY,'),
      code('    fecha           DATE NOT NULL,'),
      code('    ticker          VARCHAR(10) NOT NULL,'),
      code('    razon_rechazo   VARCHAR(50) NOT NULL,     -- rr_ratio | liquidez | earnings | volatilidad | regimen | horario | macro'),
      code('    stars_calculadas FLOAT,'),
      code('    return_forward_1d FLOAT,                 -- Qué hubiera pasado si entrábamos'),
      code('    return_forward_5d FLOAT,'),
      code('    created_at      TIMESTAMP DEFAULT NOW()'),
      code(');'),
      spacer(2),

      h2('2.3 Conexión desde Python'),
      spacer(),
      code('# requirements.txt — agregar:'),
      code('supabase>=2.0.0'),
      spacer(),
      code('# En app.py o supabase_client.py:'),
      code('from supabase import create_client'),
      code(''),
      code('SUPABASE_URL = st.secrets["SUPABASE_URL"]'),
      code('SUPABASE_KEY = st.secrets["SUPABASE_KEY"]'),
      code('supabase = create_client(SUPABASE_URL, SUPABASE_KEY)'),
      spacer(),
      code('def save_trade(trade_dict):'),
      code('    supabase.table("trades").insert(trade_dict).execute()'),
      spacer(),
      code('def save_rejected_signal(signal_dict):'),
      code('    supabase.table("signals_rejected").insert(signal_dict).execute()'),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 3: SISTEMA DE EXITS
      // ══════════════════════════════════════════════════════
      h1('3. NIVEL 2 — SISTEMA DE EXITS (El motor de rentabilidad real)'),
      spacer(),
      alertBox(
        '🎯 Principio fundamental',
        'Sin exits definidos no hay sistema de trading. Hay un sistema de compra. El bug de exits (A.csv Agilent: 2 trades en 14 años) es el error más costoso del sistema actual.',
        COLORS.lightRed, COLORS.red
      ),
      spacer(2),

      h2('3.1 Exit Layer 1 — Stop-Loss Dinámico ATR(5)'),
      spacer(),
      p('Usar ATR de 5 días (no 14) para open-to-close. Captura volatilidad reciente con más sensibilidad.'),
      spacer(),
      code('def calcular_stops(precio_entrada, atr_5, signal):'),
      code('    if signal == "LONG":'),
      code('        stop_loss = precio_entrada - (2.0 * atr_5)'),
      code('    else:  # SHORT'),
      code('        stop_loss = precio_entrada + (2.0 * atr_5)'),
      code(''),
      code('    # Filtro de coherencia: si el stop implica pérdida > 3% NO ejecutar'),
      code('    max_loss_pct = abs(precio_entrada - stop_loss) / precio_entrada * 100'),
      code('    if max_loss_pct > 3.0:'),
      code('        return None  # R:R inviable — SKIP_TRADE'),
      code(''),
      code('    return stop_loss'),
      spacer(2),

      h2('3.2 Exit Layer 2 — Trailing Stop'),
      spacer(),
      p('Se activa cuando la posición alcanza +1.0% de ganancia. El trailing stop NUNCA retrocede.'),
      spacer(),
      code('def update_trailing_stop(precio_actual, mejor_precio, atr_5, signal):'),
      code('    ganancia_pct = abs(precio_actual - precio_entrada) / precio_entrada * 100'),
      code(''),
      code('    if ganancia_pct >= 1.0:'),
      code('        if signal == "LONG":'),
      code('            nuevo_stop = precio_actual - (1.0 * atr_5)'),
      code('            trailing_stop = max(trailing_stop, nuevo_stop)  # Solo sube'),
      code('        else:  # SHORT'),
      code('            nuevo_stop = precio_actual + (1.0 * atr_5)'),
      code('            trailing_stop = min(trailing_stop, nuevo_stop)  # Solo baja'),
      code(''),
      code('    return trailing_stop'),
      spacer(2),

      h2('3.3 Exit Layer 3 — Take Profit Escalonado'),
      spacer(),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2000, 3000, 4360],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.green, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Ganancia alcanza', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.green, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Acción', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.green, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4360, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Razón', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '+1.5%', bold: true, size: 22, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Cerrar 50% de la posición', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4360, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Asegurar ganancia parcial. Mover stop del 50% restante a breakeven.', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '+2.5%', bold: true, size: 22, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Cerrar 30% adicional', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4360, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '80% cerrado con ganancia. Trailing muy ajustado en el 20% restante.', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '+4.0%+', bold: true, size: 22, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Cerrar el 100%', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4360, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'No ser codicioso en open-to-close. Tomar la ganancia completa.', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightRed, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '3:50pm ET', bold: true, size: 22, font: 'Arial', color: COLORS.red })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'HARD EXIT — cerrar TODO', bold: true, size: 20, font: 'Arial', color: COLORS.red })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4360, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Sin excepción. Últimos 10 min tienen spread amplio y volatilidad artificial.', size: 20, font: 'Arial' })] })] }),
          ]}),
        ]
      }),

      spacer(2),

      h2('3.4 Implementación del Hard Exit 3:50pm ET'),
      spacer(),
      code('HARD_EXIT_TIME = "15:50"  # ET — INNEGOCIABLE'),
      spacer(),
      code('def check_hard_exit(current_time_et):'),
      code('    if current_time_et >= HARD_EXIT_TIME:'),
      code('        close_all_positions_at_market()'),
      code('        log_exit(reason="hard_close", time=current_time_et)'),
      code('        return True'),
      code('    return False'),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 4: PRE-MARKET
      // ══════════════════════════════════════════════════════
      h1('4. NIVEL 1 — MOTOR DE DATOS PRE-MARKET (Nuevo módulo)'),
      spacer(),
      p('Archivo nuevo: lab/premarket_analyzer.py — Corre entre 8:00am y 9:15am ET todos los días de mercado.'),
      spacer(),
      p('Este es el módulo más importante para open-to-close. Las señales generadas la noche anterior se validan y enriquecen con datos pre-market reales.', { bold: true }),
      spacer(2),

      h2('4.1 Gap Pre-Market %'),
      spacer(),
      code('gap_pct = (premarket_price - prev_close) / prev_close * 100'),
      spacer(),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3000, 2160, 4200],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Rango de Gap', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Acción', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Razón', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '+0.3% a +2.0% con volumen', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '✅ LONG válido', bold: true, size: 20, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Gap moderado con convicción institucional', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '-0.3% a -2.0% con volumen', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '✅ SHORT válido', bold: true, size: 20, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Presión vendedora confirmada', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '> +3.0% o < -3.0%', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightAmber, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '⚠ Sizing -50%', bold: true, size: 20, font: 'Arial', color: COLORS.amber })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Momentum sobreextendido — riesgo de reversión', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '> ±5.0%', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightRed, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '❌ Cancelar señal', bold: true, size: 20, font: 'Arial', color: COLORS.red })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Evento binario (earnings sorpresa, FDA, M&A). No predecible.', size: 20, font: 'Arial' })] })] }),
          ]}),
        ]
      }),

      spacer(2),

      h2('4.2 Volumen Pre-Market Relativo'),
      spacer(),
      code('premarket_vol_ratio = premarket_volume / avg_premarket_volume_5d'),
      spacer(),
      bullet('Ratio > 2.0x → catalizador real presente, señal válida'),
      bullet('Ratio > 5.0x → noticia importante, verificar dirección antes de entrar'),
      bullet('Ratio < 0.5x → sin interés institucional, reducir sizing 40%'),
      spacer(2),

      h2('4.3 Sector Momentum (ETFs sectoriales)'),
      spacer(),
      p('Descargar precio pre-market de los 11 ETFs sectoriales: XLK, XLF, XLE, XLV, XLI, XLY, XLP, XLU, XLB, XLRE, XLC'),
      bullet('Candidato en top 3 sectores por momentum pre-market → bonus de convicción (+1 estrella efectiva)'),
      bullet('Candidato en bottom 3 sectores → penalizar señal (-1 estrella efectiva)'),
      spacer(2),

      h2('4.4 Validador de Gap al Open (lab/gap_validator.py — nuevo)'),
      spacer(),
      p('Corre exactamente a las 9:30am ET cuando el mercado abre:'),
      spacer(),
      code('def validate_signal_at_open(signal, entry_expected, actual_open):'),
      code('    gap_vs_signal = (actual_open - entry_expected) / entry_expected * 100'),
      code(''),
      code('    if signal == "LONG":'),
      code('        if gap_vs_signal < -2.0: return "CANCEL"         # Abrió 2% más bajo'),
      code('        if gap_vs_signal > 3.0:  return "REDUCE_SIZE_50" # Abrió 3% más alto'),
      code('        return "EXECUTE_NORMAL"'),
      code(''),
      code('    if signal == "SHORT":'),
      code('        if gap_vs_signal > 2.0:  return "CANCEL"'),
      code('        if gap_vs_signal < -3.0: return "REDUCE_SIZE_50"'),
      code('        return "EXECUTE_NORMAL"'),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 5: FILTROS DUROS
      // ══════════════════════════════════════════════════════
      h1('5. NIVEL 4 — FILTROS DUROS (Si falla cualquiera → signal = False)'),
      spacer(),
      alertBox(
        '⚠ Regla de Hierro',
        'Estos filtros son absolutos. Si cualquiera de los 8 falla, la señal se descarta SIN EXCEPCIÓN y se registra en signals_rejected con la razón. No hay "casi cumple" ni overrides manuales.',
        COLORS.lightAmber, COLORS.amber
      ),
      spacer(2),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [1440, 2400, 3120, 2400],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Filtro', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Criterio', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3120, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Código de referencia', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'razon_rechazo en DB', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '4.1 R:R', bold: true, size: 20, font: 'Arial', color: COLORS.accent })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'reward/risk >= 1.5', size: 20, font: 'Courier New', color: COLORS.darkBlue })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3120, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'if (target-entry)/(entry-stop) < 1.5: False', size: 18, font: 'Courier New', color: COLORS.darkBlue })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '"rr_ratio"', size: 20, font: 'Courier New', color: COLORS.gray })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '4.2 Liquidez', bold: true, size: 20, font: 'Arial', color: COLORS.accent })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'AvgVol(20d) >= 1M acciones y MarketCap >= $10B', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3120, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'if avg_vol < 1_000_000: False', size: 18, font: 'Courier New', color: COLORS.darkBlue })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '"liquidez"', size: 20, font: 'Courier New', color: COLORS.gray })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '4.3 Earnings', bold: true, size: 20, font: 'Arial', color: COLORS.accent })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Earnings no en próximos 7 días (margen por error Yahoo ±2 días)', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3120, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'if days_to_earnings <= 7: False', size: 18, font: 'Courier New', color: COLORS.darkBlue })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '"earnings"', size: 20, font: 'Courier New', color: COLORS.gray })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '4.4 Volatilidad', bold: true, size: 20, font: 'Arial', color: COLORS.accent })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Movimiento esperado del día >= 0.8% (ATR5/prevClose)', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3120, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'if atr_5/prev_close*100 < 0.8: False', size: 18, font: 'Courier New', color: COLORS.darkBlue })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '"volatilidad_baja"', size: 20, font: 'Courier New', color: COLORS.gray })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '4.5 Correlación', bold: true, size: 20, font: 'Arial', color: COLORS.accent })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Correlación < 0.75 con posiciones abiertas. Máx 2 del mismo sector.', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3120, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'if corr(candidato, open_pos) > 0.75: False', size: 18, font: 'Courier New', color: COLORS.darkBlue })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '"correlacion"', size: 20, font: 'Courier New', color: COLORS.gray })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '4.6 Horario', bold: true, size: 20, font: 'Arial', color: COLORS.accent })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'No entrar antes de 9:45am ni después de 3:30pm ET', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3120, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'if hora < 9:45 or hora > 15:30: False', size: 18, font: 'Courier New', color: COLORS.darkBlue })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '"horario"', size: 20, font: 'Courier New', color: COLORS.gray })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '4.7 Macro', bold: true, size: 20, font: 'Arial', color: COLORS.accent })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Bloquear si FOMC/CPI/NFP/GDP/PCE hasta 30min después del dato', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3120, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'if macro_event and hora < evento+30min: False', size: 18, font: 'Courier New', color: COLORS.darkBlue })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '"evento_macro"', size: 20, font: 'Courier New', color: COLORS.gray })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '4.8 Breadth', bold: true, size: 20, font: 'Arial', color: COLORS.accent })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'LONG: SPY no cae > 1.5% y breadth SMA20 > 35%', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3120, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'if spy_chg < -1.5% or breadth < 35: False', size: 18, font: 'Courier New', color: COLORS.darkBlue })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '"market_breadth"', size: 20, font: 'Courier New', color: COLORS.gray })] })] }),
          ]}),
        ]
      }),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 6: RÉGIMEN
      // ══════════════════════════════════════════════════════
      h1('6. NIVEL 5 — DETECTOR DE RÉGIMEN (5 Estados)'),
      spacer(),
      p('VIX tiene PRECEDENCIA ABSOLUTA sobre todas las demás métricas. Es el árbitro final del régimen.', { bold: true, color: COLORS.red }),
      spacer(2),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2000, 1440, 1440, 1440, 1440, 1600],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Régimen', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'VIX', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Min Stars', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Kelly Mult', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'ATR Stop', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Max Pos.', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '🟢 BULL FUERTE', bold: true, size: 20, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '< 15', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '13', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '1.3x', size: 20, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '2.0 ATR', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '5', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: 'E8F8E8', type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '🟡 BULL DÉBIL', bold: true, size: 20, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '15-20', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '14', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '1.0x', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '2.0 ATR', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '4', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightAmber, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '🟠 LATERAL', bold: true, size: 20, font: 'Arial', color: COLORS.amber })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '20-25', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '15', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '0.6x', size: 20, font: 'Arial', color: COLORS.amber })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '1.5 ATR', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '3', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightRed, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '🔴 BEAR SUAVE', bold: true, size: 20, font: 'Arial', color: COLORS.red })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '25-30', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '17', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '0.3x', size: 20, font: 'Arial', color: COLORS.red })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '1.5 ATR', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '2', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 2000, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '⛔ BEAR FUERTE', bold: true, size: 20, font: 'Arial', color: COLORS.white })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '> 30', size: 20, font: 'Arial', color: COLORS.red, bold: true })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '99 (bloqueado)', size: 20, font: 'Arial', color: COLORS.red })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '0.0x', size: 20, font: 'Arial', color: COLORS.red, bold: true })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '1.0 ATR', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 1600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '0 (NO OPERAR)', bold: true, size: 20, font: 'Arial', color: COLORS.red })] })] }),
          ]}),
        ]
      }),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 7: HALF-KELLY
      // ══════════════════════════════════════════════════════
      h1('7. NIVEL 3 — SIZING DINÁMICO (Half-Kelly Calibrado)'),
      spacer(),

      h2('7.1 Fórmula Base (rolling 20 trades)'),
      spacer(),
      code('# Siempre calculado sobre las últimas 20 operaciones completadas'),
      code('win_rate  = trades_ganadores / total_trades'),
      code('avg_win   = mean(retornos_positivos)'),
      code('avg_loss  = mean(abs(retornos_negativos))'),
      spacer(),
      code('edge           = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)'),
      code('kelly_fraction = edge / avg_win'),
      code('half_kelly     = kelly_fraction / 2'),
      spacer(),
      code('# Límites de seguridad SIEMPRE aplicados'),
      code('half_kelly = max(0.02, min(half_kelly, 0.20))  # Entre 2% y 20% del capital'),
      code('position_size = capital_disponible * half_kelly * regime_mult * confidence_mult'),
      spacer(2),

      h2('7.2 Multiplicadores'),
      spacer(),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3600, 2880, 2880],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Condición', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Multiplicador', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2880, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Categoría', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          ...[ 
            ['Régimen BULL FUERTE', '1.3x', 'Régimen'],
            ['Régimen BULL DÉBIL', '1.0x', 'Régimen'],
            ['Régimen LATERAL', '0.6x', 'Régimen'],
            ['Régimen BEAR SUAVE', '0.3x', 'Régimen'],
            ['Régimen BEAR FUERTE', '0.0x (NO OPERAR)', 'Régimen'],
            ['Convicción 5 estrellas', '1.2x', 'Convicción'],
            ['Convicción 4 estrellas', '1.0x', 'Convicción'],
            ['Convicción 3 estrellas', '0.7x', 'Convicción'],
            ['Convicción 1-2 estrellas', '0.0x (NO OPERAR)', 'Convicción'],
            ['Volumen pre-market > 5x', '0.5x', 'Volumen'],
            ['Volumen pre-market 2-5x', '1.1x', 'Volumen'],
            ['Volumen pre-market normal', '1.0x', 'Volumen'],
            ['Volumen pre-market < 0.5x', '0.6x', 'Volumen'],
          ].map((row, i) => new TableRow({ children: row.map((text, j) => new TableCell({
            borders,
            shading: { fill: i % 2 === 0 ? COLORS.white : COLORS.lightGray, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            width: { size: [3600, 2880, 2880][j], type: WidthType.DXA },
            children: [new Paragraph({ children: [new TextRun({ text, size: 20, font: j === 1 ? 'Courier New' : 'Arial', bold: j === 1, color: text.includes('0.0x') ? COLORS.red : text.includes('1.3x') || text.includes('1.2x') || text.includes('1.1x') ? COLORS.green : COLORS.black })] })]
          }))})
          )
        ]
      }),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 8: INDICADORES NUEVOS
      // ══════════════════════════════════════════════════════
      h1('8. NIVEL 10 — INDICADORES NUEVOS PARA OPEN-TO-CLOSE'),
      spacer(),
      p('El sistema actual tiene RSI, MACD, SMA20/50, Gap%, Vol relativo. Agregar los siguientes:'),
      spacer(2),

      h2('8.1 VWAP (Volume Weighted Average Price)'),
      spacer(),
      p('El precio de referencia institucional intraday. El indicador más utilizado por market makers y fondos.'),
      spacer(),
      code('# Calculado desde el open de cada sesión'),
      code('vwap = sum(precio_tipico_i * volumen_i) / sum(volumen_i)'),
      code('precio_tipico = (high + low + close) / 3'),
      spacer(),
      bullet('Precio sobre VWAP → sesgo alcista institucional → favorece LONG'),
      bullet('Precio bajo VWAP → sesgo bajista → favorece SHORT'),
      bullet('Señal LONG requiere precio > VWAP al momento de entrada'),
      spacer(2),

      h2('8.2 ATR(5) — Volatilidad Reciente'),
      spacer(),
      code('atr_5 = calcular_ATR(highs, lows, closes, periodo=5)'),
      bullet('Dimensiona todos los stops (ver Sección 3)'),
      bullet('Valida si el target de 1% es alcanzable hoy'),
      bullet('Si ATR(5)/prev_close < 0.8% → Filtro 4.4 rechaza la señal'),
      spacer(2),

      h2('8.3 Relative Strength vs SPY'),
      spacer(),
      code('rs_1m  = ticker_return_1m  - spy_return_1m'),
      code('rs_3m  = ticker_return_3m  - spy_return_3m'),
      spacer(),
      bullet('RS > 0 en ambos períodos → acción líder de mercado → mejor candidata LONG'),
      bullet('RS < 0 en ambos períodos → acción rezagada → evitar LONG, considerar SHORT'),
      spacer(2),

      h2('8.4 Posición en Rango 52 Semanas'),
      spacer(),
      code('pct_52w = (precio - low_52w) / (high_52w - low_52w) * 100'),
      spacer(),
      bullet('pct_52w > 85% con volumen alto → breakout potencial → bonus LONG'),
      bullet('pct_52w < 15% con volumen decreciente → reversión potencial → evaluar LONG'),
      bullet('pct_52w entre 40-60% sin catalizador → señal débil, reducir convicción'),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 9: CIRCUIT BREAKERS
      // ══════════════════════════════════════════════════════
      h1('9. NIVEL 9 — GESTIÓN DE PORTAFOLIO + CIRCUIT BREAKERS'),
      spacer(),

      h2('9.1 Reglas de Portafolio'),
      spacer(),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3600, 2160, 3600],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Regla', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Valor', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Razón', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          ...[ 
            ['Máx posiciones simultáneas', '5', 'Diversificación sin diluir edge'],
            ['Máx posiciones mismo sector', '2', 'Evitar concentración sectorial'],
            ['Máx capital por posición', '20% del capital', 'Una mala señal no destruye la cuenta'],
            ['Mínimo en cash', '20% siempre', 'Capacidad de actuar ante oportunidades'],
            ['Circuit breaker pérdida día', '-3% del capital', 'Cerrar todo y parar si el día es adverso'],
            ['Circuit breaker VIX spike', 'VIX ≥ 35 intradía', 'Mercado en pánico = no predecible'],
            ['Circuit breaker SPY caída', 'SPY cae -2.5% desde open', 'Evento sistémico, no idiosincrático'],
          ].map((row, i) => new TableRow({ children: row.map((text, j) => new TableCell({
            borders,
            shading: { fill: i % 2 === 0 ? COLORS.white : COLORS.lightGray, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            width: { size: [3600, 2160, 3600][j], type: WidthType.DXA },
            children: [new Paragraph({ children: [new TextRun({ text, size: 20, font: j === 1 ? 'Courier New' : 'Arial', color: COLORS.black })] })]
          }))})
          )
        ]
      }),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 10: BACKTESTING
      // ══════════════════════════════════════════════════════
      h1('10. NIVEL 7 — BACKTESTING HONESTO (Sin Sesgo de Supervivencia)'),
      spacer(),

      alertBox(
        '⚠ El error más común en backtesting',
        'Usar la lista ACTUAL del S&P 500 aplicada hacia atrás. Esto introduce sesgo de supervivencia masivo porque solo incluye empresas que sobrevivieron hasta hoy. Si en 2010 hubieras sabido que TSLA y NVDA llegarían a donde están, habrías sido billonario. Fuente gratuita de composición histórica: github.com/fja05680/sp500',
        COLORS.lightRed, COLORS.red
      ),
      spacer(2),

      h2('10.1 División de Datos Obligatoria'),
      spacer(),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 2400, 2400, 2160],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Set', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Período', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Uso', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Restricción', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'TRAIN (60%)', bold: true, size: 20, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '2010 – 2019', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Calibrar parámetros', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Uso libre', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightAmber, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'VALIDATION (20%)', bold: true, size: 20, font: 'Arial', color: COLORS.amber })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '2020 – 2022', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Ajuste fino', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Máx 5 iteraciones', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightRed, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'TEST OOS (20%)', bold: true, size: 20, font: 'Arial', color: COLORS.red })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '2023 – 2024', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Validación final', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '1 SOLA VEZ. Nunca más.', bold: true, size: 20, font: 'Arial', color: COLORS.red })] })] }),
          ]}),
        ]
      }),

      spacer(2),

      h2('10.2 Métricas Mínimas — El Backtest es Inválido sin Todas'),
      spacer(),
      bullet('Total trades (mínimo 50 para significancia estadística)'),
      bullet('Win rate %'),
      bullet('Average win % y Average loss %'),
      bullet('Profit factor (sum_wins / sum_losses)'),
      bullet('Sharpe Ratio anualizado'),
      bullet('Sortino Ratio (solo penaliza downside)'),
      bullet('Max Drawdown % y duración en días'),
      bullet('CAGR vs SPY buy-and-hold en el mismo período'),
      bullet('Retorno desglosado por régimen de mercado'),
      bullet('Hit rate por día de la semana (valida filtro lunes/viernes)'),
      bullet('Transaction costs incluidos: mega cap 0.05%, large 0.15%, mid 0.30%'),
      spacer(2),

      h2('10.3 Criterios de Aprobación para Dinero Real'),
      spacer(),
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [3120, 2400, 3840],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3120, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Métrica', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Mínimo requerido', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3840, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Si no se cumple', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          ...[ 
            ['Sharpe Ratio anualizado', '≥ 1.5', 'No ir a dinero real'],
            ['Max Drawdown', '≤ -15%', 'No ir a dinero real'],
            ['Win Rate', '≥ 52%', 'Revisar filtros y señales'],
            ['Profit Factor', '≥ 1.3', 'Revisar exits y take profits'],
            ['Alpha sobre SPY', '≥ +5% CAGR', 'El sistema no agrega valor'],
            ['Trades mínimos en test', '≥ 50', 'Resultado no estadísticamente significativo'],
          ].map((row, i) => new TableRow({ children: row.map((text, j) => new TableCell({
            borders,
            shading: { fill: i % 2 === 0 ? COLORS.white : COLORS.lightGray, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            width: { size: [3120, 2400, 3840][j], type: WidthType.DXA },
            children: [new Paragraph({ children: [new TextRun({ text, size: 20, font: 'Arial', color: COLORS.black })] })]
          }))})
          )
        ]
      }),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 11: ORDEN DE IMPLEMENTACIÓN
      // ══════════════════════════════════════════════════════
      h1('11. ORDEN DE IMPLEMENTACIÓN ESTRICTO'),
      spacer(),
      alertBox(
        '📌 Instrucción para Antigravity',
        'Implementar en el orden exacto de esta tabla. No saltarse semanas ni combinar niveles de distintas semanas. Cada semana tiene un criterio de completado — no pasar a la siguiente sin completarlo.',
        COLORS.lightBlue, COLORS.accent
      ),
      spacer(2),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [1200, 1800, 3960, 2400],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Semana', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Niveles', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3960, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Tareas específicas', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Criterio de completado', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightRed, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'S1', bold: true, size: 24, font: 'Arial', color: COLORS.red })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Nivel 0 + Supabase', bold: true, size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3960, type: WidthType.DXA }, children: [
              new Paragraph({ children: [new TextRun({ text: '• Bug 0.1: Eliminar proxy sintético (cascada real)', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Bug 0.2: Reemplazar lru_cache con st.cache_data', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Bug 0.3: Monte Carlo bootstrap', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Bug 0.4: Diagnóstico real', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Crear tablas trades + signals_rejected en Supabase', size: 18, font: 'Arial' })] }),
            ] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Diagnóstico muestra latencia real. Cache persiste. Supabase recibe inserts.', size: 18, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightRed, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'S2', bold: true, size: 24, font: 'Arial', color: COLORS.red })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Nivel 2 + Nivel 9', bold: true, size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3960, type: WidthType.DXA }, children: [
              new Paragraph({ children: [new TextRun({ text: '• Exits: ATR(5) stop + trailing + take profit escalonado', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Hard exit 3:50pm ET innegociable', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Circuit breakers: pérdida día -3%, VIX ≥35, SPY -2.5%', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Reglas de portafolio (max 5 pos, max 20% por pos)', size: 18, font: 'Arial' })] }),
            ] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Backtest básico muestra trades con exits reales (no 2 en 14 años).', size: 18, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightAmber, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'S3', bold: true, size: 24, font: 'Arial', color: COLORS.amber })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Nivel 1 + Nivel 4', bold: true, size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3960, type: WidthType.DXA }, children: [
              new Paragraph({ children: [new TextRun({ text: '• premarket_analyzer.py: gap%, vol relativo, sector momentum', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• gap_validator.py: validación al open 9:30am', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Los 8 filtros duros (R:R, liquidez, earnings, etc.)', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Registro de señales rechazadas en Supabase', size: 18, font: 'Arial' })] }),
            ] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Cada señal rechazada queda en DB con razón. Filtros eliminan al menos 30% de señales débiles.', size: 18, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightAmber, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'S4', bold: true, size: 24, font: 'Arial', color: COLORS.amber })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Nivel 5 + Nivel 3', bold: true, size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3960, type: WidthType.DXA }, children: [
              new Paragraph({ children: [new TextRun({ text: '• Detector de 5 regímenes con VIX como árbitro', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Lógica de transición de régimen (no cierra posiciones abiertas)', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Half-Kelly rolling 20 trades con multiplicadores', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Protocolo de quemado inicial (paper trading obligatorio)', size: 18, font: 'Arial' })] }),
            ] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Sistema detecta régimen correctamente para 2020 (crash COVID) y 2022 (bear market).', size: 18, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'S5', bold: true, size: 24, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Nivel 10 + Nivel 6', bold: true, size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3960, type: WidthType.DXA }, children: [
              new Paragraph({ children: [new TextRun({ text: '• VWAP, ATR(5), RS vs SPY, posición 52w en fetchYahoo()', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Sistema de pesos fundamentales (FCF: 3x, deuda: 3x, etc.)', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Reemplazar conteo simple de stars por score ponderado', size: 18, font: 'Arial' })] }),
            ] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Score ponderado visible en UI. VWAP aparece en tabla de señales.', size: 18, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'S6', bold: true, size: 24, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Nivel 7 + Nivel 8', bold: true, size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3960, type: WidthType.DXA }, children: [
              new Paragraph({ children: [new TextRun({ text: '• Backtesting con historical constituents (github fja05680/sp500)', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Train/Val/Test split. Test OOS toca UNA sola vez.', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Paper trading persistente con slippage realista', size: 18, font: 'Arial' })] }),
            ] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Backtest TRAIN pasa todos los criterios de la Sección 10.3.', size: 18, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'S7-10', bold: true, size: 24, font: 'Arial', color: COLORS.accent })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Paper Trading Activo', bold: true, size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3960, type: WidthType.DXA }, children: [
              new Paragraph({ children: [new TextRun({ text: '• Mínimo 30 trades antes de evaluar', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Calibración de pesos con datos reales', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Análisis de señales rechazadas: ¿umbral demasiado alto?', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Ajuste de umbrales por régimen basado en resultados', size: 18, font: 'Arial' })] }),
            ] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '30 trades con Sharpe > 1.5 y Max DD < 15%.', size: 18, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1200, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'S11+', bold: true, size: 24, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Dinero Real', bold: true, size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3960, type: WidthType.DXA }, children: [
              new Paragraph({ children: [new TextRun({ text: '• Empezar con 25% del capital real objetivo', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Si 20 trades reales pasan criterios → 100% del capital', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Revisión mensual de métricas rolling', size: 18, font: 'Arial' })] }),
              new Paragraph({ children: [new TextRun({ text: '• Si Sharpe cae < 1.0 por 2 semanas → volver a paper trading', size: 18, font: 'Arial' })] }),
            ] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Continuo. Nunca se "termina"  — el mercado cambia.', size: 18, font: 'Arial' })] })] }),
          ]}),
        ]
      }),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 12: RESUMEN DE IMPACTO
      // ══════════════════════════════════════════════════════
      h1('12. RESUMEN DE IMPACTO ESPERADO POR NIVEL'),
      spacer(),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [1440, 3120, 4800],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 1440, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Nivel', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 3120, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Cambio implementado', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4800, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Impacto esperado en rentabilidad', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          ...[ 
            ['0 — Bug fixes', 'Eliminar proxy sintético + reparar exits', '🔴 CRÍTICO: Sin esto nada funciona. El sistema genera señales falsas y nunca cierra trades.'],
            ['1 — Pre-market', 'Módulo 8:00-9:15am ET + gap validator', '+15-20% hit rate. Filtra señales invalidadas overnight antes de perder dinero en ellas.'],
            ['2 — Exits', 'ATR(5) stop + trailing + TP escalonado + hard 3:50', '+++ protección de capital. Elimina los drawdowns de -35% por posiciones que nunca cierran.'],
            ['3 — Half-Kelly', 'Sizing dinámico rolling 20 trades', '+20-30% retorno ajustado. Apuesta más en setups de alta convicción probados.'],
            ['4 — Filtros duros', '8 filtros: R:R, liquidez, earnings, etc.', '+10-15% win rate. Elimina systematicamente los trades con expectativa negativa.'],
            ['5 — 5 regímenes', 'VIX árbitro + 5 estados con parámetros', '+++ supervivencia. No operar en bear market = no perder en bear market.'],
            ['6 — Pesos fundamentales', 'FCF 3x, deuda 3x, ROE 2x, etc.', '+5-10% signal quality. Score más preciso = mejores candidatos seleccionados.'],
            ['7 — Backtesting honesto', 'Historical constituents + OOS split', 'Invaluable. Saber si el edge es real ANTES de poner dinero real.'],
            ['8 — Paper trading', 'Supabase persistente + slippage real', 'Invaluable. 30 trades de validación sin riesgo de capital.'],
            ['9 — Portfolio rules', 'Max 5 pos + circuit breakers', '+++ protección sistémica. Una señal mala no destruye la cuenta.'],
            ['10 — VWAP + RS + ATR5', 'Indicadores críticos para intraday', '+10% hit rate. Alineación con institucionales via VWAP.'],
          ].map((row, i) => new TableRow({ children: row.map((text, j) => new TableCell({
            borders,
            shading: { fill: i % 2 === 0 ? COLORS.white : COLORS.lightGray, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: 120, right: 120 },
            width: { size: [1440, 3120, 4800][j], type: WidthType.DXA },
            children: [new Paragraph({ children: [new TextRun({ 
              text, size: 20, font: 'Arial', 
              bold: j === 0,
              color: j === 0 ? COLORS.accent : COLORS.black 
            })] })]
          }))})
          )
        ]
      }),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 13: PREGUNTAS ABIERTAS
      // ══════════════════════════════════════════════════════
      h1('13. PREGUNTAS QUE DEBES RESPONDER ANTES DE SEMANA 3'),
      spacer(),
      p('Las siguientes decisiones afectan la implementación de niveles específicos. Responder antes de que Antigravity llegue a la semana indicada.', { italic: true, color: COLORS.gray }),
      spacer(2),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [600, 4080, 2280, 2400],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 100, right: 100 }, width: { size: 600, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '#', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 4080, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Pregunta', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2280, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Opciones', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Impacta', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          ...[ 
            ['1', 'Drawdown máximo tolerable. Calibra el multiplicador Half-Kelly.', 'Conservador: DD<15% | Moderado: DD<20% | Agresivo: DD<25%', 'Nivel 3 (Half-Kelly)'],
            ['2', '¿Cuánto capital simulado para paper trading? Debe ser representativo del capital real futuro.', '$10,000 / $50,000 / $100,000+', 'Nivel 8 (paper trading)'],
            ['3', '¿Dónde corre el motor pre-market 8:00-9:15am ET? Debe ser un proceso schedulado diariamente.', 'Render free | Railway | VPS propio', 'Nivel 1 (pre-market)'],
            ['4', 'Yahoo Finance no da ticks en tiempo real gratis. ¿Cómo se monitoreará stops intraday?', 'Polling cada 1-5min | Websocket Polygon.io/Alpaca', 'Nivel 2 (exits intraday)'],
          ].map((row, i) => new TableRow({ children: row.map((text, j) => new TableCell({
            borders,
            shading: { fill: i % 2 === 0 ? COLORS.white : COLORS.lightGray, type: ShadingType.CLEAR },
            margins: { top: 80, bottom: 80, left: j === 0 ? 100 : 120, right: 120 },
            width: { size: [600, 4080, 2280, 2400][j], type: WidthType.DXA },
            children: [new Paragraph({ children: [new TextRun({ text, size: 20, font: 'Arial', bold: j === 0, color: j === 0 ? COLORS.accent : COLORS.black })] })]
          }))})
          )
        ]
      }),

      spacer(2),
      pageBreak(),

      // ══════════════════════════════════════════════════════
      // SECCIÓN 14: SLIPPAGE Y ESCALADO
      // ══════════════════════════════════════════════════════
      h1('14. SLIPPAGE REALISTA + ESCALADO A DINERO REAL'),
      spacer(),

      h2('14.1 Tabla de Slippage por Capitalización'),
      spacer(),
      p('Aplicar en todos los backtests y paper trades. Sin slippage realista, el backtest es optimista.'),
      spacer(),

      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [2400, 2160, 2400, 2400],
        rows: [
          new TableRow({ tableHeader: true, children: [
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Categoría', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Market Cap', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Slippage', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Ejemplos', bold: true, size: 20, color: COLORS.white, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightGreen, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Mega Cap', bold: true, size: 20, font: 'Arial', color: COLORS.green })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '> $500B', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '0.05% (5 bps)', size: 20, font: 'Courier New', color: COLORS.accent })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'AAPL, MSFT, NVDA, GOOGL, AMZN, META', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightAmber, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Large Cap', bold: true, size: 20, font: 'Arial', color: COLORS.amber })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '$50B – $500B', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '0.15% (15 bps)', size: 20, font: 'Courier New', color: COLORS.accent })] })] }),
            new TableCell({ borders, shading: { fill: COLORS.lightGray, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Top 100 S&P 500', size: 20, font: 'Arial' })] })] }),
          ]}),
          new TableRow({ children: [
            new TableCell({ borders, shading: { fill: COLORS.lightRed, type: ShadingType.CLEAR }, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Mid Cap', bold: true, size: 20, font: 'Arial', color: COLORS.red })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2160, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '$10B – $50B', size: 20, font: 'Arial' })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: '0.30% (30 bps)', size: 20, font: 'Courier New', color: COLORS.red })] })] }),
            new TableCell({ borders, margins: { top: 80, bottom: 80, left: 120, right: 120 }, width: { size: 2400, type: WidthType.DXA }, children: [new Paragraph({ children: [new TextRun({ text: 'Resto del S&P 500', size: 20, font: 'Arial' })] })] }),
          ]}),
        ]
      }),

      spacer(2),

      h2('14.2 Protocolo de Escalado a Dinero Real'),
      spacer(),
      numbered('Paper trading hasta 30 trades completados (mínimo)'),
      numbered('Calcular Sharpe, Max DD, Win Rate sobre esos 30 trades'),
      numbered('Si pasa todos los criterios de la Sección 10.3 → dinero real con 25% del capital'),
      numbered('Si 20 trades reales también pasan los criterios → escalar a 100% del capital'),
      numbered('Revisión mensual de métricas rolling. Si Sharpe < 1.0 por 2 semanas consecutivas → volver a paper trading'),

      spacer(2),
      spacer(2),

      // Cierre
      new Table({
        width: { size: 9360, type: WidthType.DXA },
        columnWidths: [9360],
        rows: [
          new TableRow({
            children: [new TableCell({
              borders: {
                top: { style: BorderStyle.SINGLE, size: 8, color: COLORS.blue },
                bottom: { style: BorderStyle.SINGLE, size: 8, color: COLORS.blue },
                left: { style: BorderStyle.SINGLE, size: 8, color: COLORS.blue },
                right: { style: BorderStyle.SINGLE, size: 8, color: COLORS.blue },
              },
              shading: { fill: COLORS.darkBlue, type: ShadingType.CLEAR },
              margins: { top: 200, bottom: 200, left: 360, right: 360 },
              width: { size: 9360, type: WidthType.DXA },
              children: [
                new Paragraph({
                  alignment: AlignmentType.CENTER,
                  children: [new TextRun({ text: 'PLAN MAESTRO v4.0 — COMPLETO', bold: true, size: 28, color: COLORS.white, font: 'Arial' })]
                }),
                new Paragraph({
                  alignment: AlignmentType.CENTER,
                  children: [new TextRun({ text: 'Para implementación directa por Antigravity · Sistema Open-to-Close S&P 500', size: 22, color: 'AAAAAA', font: 'Arial', italics: true })]
                }),
                new Paragraph({
                  alignment: AlignmentType.CENTER,
                  spacing: { before: 80 },
                  children: [new TextRun({ text: 'Cualquier duda sobre implementación específica: preguntar antes de codificar.', size: 20, color: 'AAAAAA', font: 'Arial' })]
                }),
              ]
            })]
          })
        ]
      }),

    ]
  }]
});

Packer.toBuffer(doc).then(buffer => {
  fs.writeFileSync('/mnt/user-data/outputs/PLAN_MAESTRO_v4_ANTIGRAVITY.docx', buffer);
  console.log('Done');
});
