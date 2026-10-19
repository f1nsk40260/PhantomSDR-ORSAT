---
pdf: guideAnalyseurES.pdf
pdf_title: PhantomSDR-ORSAT — Guía del analizador de audio
title: Analizador de audio ORSAT
subtitle: Guía detallada — espectro, informe de modulación SSB e informe de escucha
url: https://orsat.ddns.net
cover: analyseur_usb.jpg
cover_caption: El analizador de audio en USB: espectro, marcas de ancho de banda, voz media e informe de modulación.
summary: Esta guía explica cómo leer el analizador de audio de ORSAT, juzgar la modulación de una estación (equilibrio tonal, compresión, zumbido, portadora, banda opuesta, splatter), comparar dos ajustes y enviar un informe de escucha con un fragmento de audio.
edition: Versión española — Edición octubre 2026 — ORSAT 1.0
credits: Módulo desarrollado por **F1NSK** para ORSAT, a partir de PhantomSDR-Plus de **SV1BTL**.
header_left: ORSAT — Guía del analizador de audio
header_right: ORSAT 1.0
page: Página
toc: Índice
---

# 1. Presentación

El **analizador de audio** muestra y mide la señal de la estación que usted escucha. Sirve para dos cosas:

- **ver** la señal: espectro de audio, frecuencia base, ancho de banda, filtro del receptor;
- **juzgar** una modulación SSB: un informe con cifras, criterio por criterio, con un veredicto claro y un informe para enviar al corresponsal.

Se encuentra en la columna derecha de la interfaz, bajo el título **ANALIZADOR DE AUDIO**. El botón **📊 Show** lo abre encima de los paneles, **📊 Hide** lo cierra. El cursor **Ganancia** solo ajusta la altura de la visualización.

## 1.1 Un analizador que trabaja sobre el audio bruto

El analizador recibe el sonido del receptor **antes** de todos los procesados de escucha: silencio, squelch, AGC del navegador, reducción de ruido, notch, ecualizador. Dos consecuencias:

- sus ajustes de escucha no falsean las medidas: se juzga la estación, no su comodidad de escucha;
- el analizador **sigue funcionando con el sonido silenciado**.

> [Nota] El único procesado que sigue siendo visible es el **filtro de recepción**, aplicado por el servidor antes de enviar el sonido. El analizador lo muestra y lo tiene en cuenta.

## 1.2 Una visualización que se adapta al modo

| Modo | Lo que muestra el analizador |
| USB, LSB | Espectro de audio, marcas SSB y ESSB, informe de audio SSB completo |
| CW | Espectro de audio centrado en la nota de 750 Hz, marcas de ancho CW |
| AM, FM | Vista RF: portadora en el centro, bandas laterales a cada lado |

# 2. Puesta en marcha rápida

1. Sintonice la estación y elija el modo (USB o LSB para un informe completo).
2. En la columna derecha, haga clic en **📊 Show** bajo **ANALIZADOR DE AUDIO**.
3. Haga zoom en la cascada sobre la estación: el ancho ocupado, la portadora y la banda opuesta se miden en la cascada, que debe ser lo bastante fina.
4. Deje hablar a la estación: los veredictos aparecen tras **3 segundos de voz**.
5. Para enviar el resultado, haga clic en **🎧 Generar un informe de escucha**.

> [Consejo] Para analizar **su propia emisión**, escúchese en ORSAT y haga clic en **Silenciar** en la franja superior: nada vuelve a su micrófono y el análisis continúa.

# 3. La franja «Frecuencia base»

En la parte superior del analizador, una franja recuerda:

- la **frecuencia base**, la del dial, en cifras grandes;
- el **modo** en una pastilla dorada;
- una breve explicación: «0 Hz audio = portadora» en USB, el eje invertido en LSB, la nota de 750 Hz en CW, la vista RF en AM y FM.

A la derecha, el botón **🔊 Silenciar** corta el sonido del receptor. Pasa a rojo, **🔇 Silenciado**, mientras el sonido está cortado. Es el mismo ajuste que el botón de silencio del receptor: ambos quedan sincronizados. Si el sonido se cortó desde este botón, **vuelve automáticamente al cerrar el analizador**.

# 4. Leer el espectro en USB

![Espectro de audio en USB con la lectura al pasar el ratón, las marcas SSB y ESSB, el filtro actual y la curva de voz media.](images/analyseur_usb.jpg){w=482}

- **Eje horizontal**: frecuencia de audio, de 0 a 4,5 kHz. **Eje vertical**: nivel en dB.
- **Relleno de color**: el espectro instantáneo. **Línea clara**: el pico, que baja lentamente.
- **Línea dorada «Base»**: la frecuencia base, en 0 Hz de audio, es decir la portadora suprimida de la estación.
- **Marcas**: **SSB estándar 300–2700 Hz** (dorada) y **ESSB 50–4000 Hz** (azul, discontinua).
- **Recuadro de puntos blancos**: el **filtro actual** del receptor, con sus límites abajo a la derecha.
- **Curva azul «voz media»**: la forma media de la voz en los últimos segundos, calculada por el informe SSB.
- **Al pasar el ratón**: una burbuja da la **frecuencia RF exacta** del punto y su frecuencia de audio.

Bajo el espectro, una línea da el **ancho ocupado** medido y su veredicto (véase el capítulo 7).

# 5. LSB y CW

## 5.1 LSB: el eje está invertido

![En LSB, los agudos están a la izquierda y la portadora a la derecha, como en la cascada.](images/analyseur_lsb.jpg){w=482}

En LSB la voz está por debajo de la portadora. Para que el analizador se lea en el mismo sentido que la cascada, el eje está **invertido**: la frecuencia base (0 Hz de audio) está a la derecha y los agudos a la izquierda. Las medidas y el informe son idénticos a los de USB.

## 5.2 CW

![En CW, el eje va de 0 a 2 kHz y la línea dorada marca la nota de 750 Hz.](images/analyseur_cw.jpg){w=482}

En CW el eje va de 0 a 2 kHz. La línea dorada marca la **nota de 750 Hz**, que corresponde a la frecuencia del dial. Las marcas **CW 500 Hz** y **CW 250 Hz** muestran los filtros habituales. El ancho ocupado sirve para detectar los **clics de manipulación**: una emisión CW limpia se mantiene por debajo de 300 Hz a −26 dB.

# 6. AM y FM: la vista RF

![En AM, la portadora está en el centro y las dos bandas laterales se extienden a cada lado.](images/analyseur_am.jpg){w=482}

En AM y FM, el audio demodulado ya no contiene la portadora. Pasa a 0 Hz y las dos bandas laterales se superponen. El analizador cambia entonces **automáticamente** a una **vista RF**, tomada de la cascada:

- **la portadora en el centro** (línea dorada), las bandas laterales a izquierda y derecha;
- un eje graduado en **desplazamiento respecto a la portadora** (−6k … 0 … +6k) y un nivel en **dB sobre el ruido**;
- marcas simétricas: AM radiodifusión **±4,5 kHz** y AM radioaficionado **±3 kHz**, FM estrecha **±5,5 kHz** (ancho de Carson), FM ancha **±100 kHz**;
- el filtro actual, simétrico, y el posible splatter a ambos lados.

Ancho mostrado: ±6 kHz en AM, ±8 kHz en FM, ±120 kHz en FM ancha. La simetría de las bandas laterales y el nivel de portadora se leen de un vistazo.

> [Consejo] La vista RF necesita una cascada fina: al menos 50 puntos en el ancho mostrado, es decir 240 Hz por punto como máximo en AM. Si no, el analizador indica que hay que hacer zoom sobre la estación en la cascada.

# 7. Ancho ocupado y splatter

![Una estación demasiado ancha: el desbordamiento aparece en rojo y la línea de estado indica un splatter probable.](images/analyseur_splat.jpg){w=482}

El analizador mide en la cascada el **ancho ocupado** por la estación: el ancho en el que su espectro supera el nivel situado 26 dB por debajo de su pico (método habitual de las normas de emisión). La medida:

- abarca 6 segundos y retiene un ancho que el 80 % de las medidas no supera: un pico aislado no cuenta;
- ignora las trazas levantadas por un **parásito estático**;
- espera 2 segundos de medidas antes de dar un veredicto.

| Modo | Conforme | Algo ancho | Splatter probable |
| SSB | hasta 3,3 kHz | hasta 5 kHz | más de 5 kHz |
| AM | hasta 10 kHz | hasta 12 kHz | más de 12 kHz |
| CW | hasta 0,3 kHz | hasta 0,6 kHz | más (clics de manipulación) |

En el espectro, la parte que desborda se tiñe de **ámbar** (algo ancho) o de **rojo** (splatter).

# 8. El informe de audio SSB

En USB y LSB, el recuadro **INFORME DE AUDIO SSB** analiza la modulación durante los **últimos 20 segundos**, y **solo mientras la estación habla**. Los veredictos aparecen tras 3 s de voz. Cada línea lleva un piloto: **verde** (bien), **ámbar** (a vigilar), **rojo** (defecto), **gris** (no medible, con el motivo).

## 8.1 Los criterios

| Criterio | Qué se mide | Verde | Ámbar | Rojo |
| Graves 100–300 Hz | Energía de los graves respecto a los medios (300–1500 Hz), comparada con la referencia | diferencia ≤ 4 dB | diferencia ≤ 8 dB | más |
| Presencia 1,5–2,7 kHz | Energía de la presencia respecto a los medios | diferencia ≤ 4 dB | diferencia ≤ 8 dB | más |
| Compresión | Relación pico / media de la voz | 10 a 15 dB | más de 15 dB | menos de 10 dB |
| Zumbido de red | Rayas estables en 50/100/150 Hz o 60/120/180 Hz | ausente | — | detectado |
| Portadora residual | Nivel de la portadora bajo los picos de voz | ≥ 40 dB | 30 a 40 dB | < 30 dB |
| Banda opuesta | Energía de la otra banda lateral | ≥ 40 dB | 30 a 40 dB | < 30 dB |
| Ancho ocupado | Medida del capítulo 7 | conforme | algo ancho | splatter |

**Cómo leer los veredictos:**

- **Graves**: «demasiados graves» da una voz apagada y desperdicia potencia; «faltan graves» da una voz fina.
- **Presencia**: «falta presencia» da una voz ahogada, poco legible en DX; «demasiados agudos» da una voz chillona.
- **Compresión**: «poca o ninguna compresión» es natural pero se abre paso peor; «muy comprimido, probable recorte» indica un compresor demasiado alto, a menudo con un ruido de fondo que sube en las pausas.
- **Zumbido**: un defecto de masa o de alimentación en el corresponsal.
- **Portadora residual** y **banda opuesta**: se miden en la cascada, porque el filtro de recepción las oculta en el audio. Un valor precedido de «<» significa que el defecto está bajo el ruido: solo se sabe que es al menos tan bueno como el valor mostrado. Si la otra banda lateral la ocupa otra estación, el analizador lo indica (QRM) en lugar de culpar al corresponsal.

## 8.2 La referencia tonal

La fila de botones **Juzgar la voz respecto a:**, al principio del informe, elige la curva tonal con la que se compara la voz; el botón dorado es la referencia activa:

| Referencia | Graves / medios | Presencia / medios | Para qué uso |
| SSB estándar | −13 dB | −10 dB | Tráfico habitual, filtro 300–2700 Hz |
| DX / punch | −16 dB | −6 dB | Presencia reforzada para abrirse paso en el ruido |
| ESSB / hi-fi | −3 dB | −12 dB | Banda ancha, graves conservados |

Un mismo ajuste puede ser «equilibrado» en ESSB y tener «demasiados graves» en DX: elija la referencia que corresponde a lo que quiere hacer el corresponsal.

## 8.3 Los parásitos estáticos

Los chasquidos de parásitos (muy breves, de espectro plano) se detectan y se **descartan** del informe. Las relaciones de graves y presencia se calculan además como **mediana**: un parásito que escapara al filtro no desplaza el resultado. Cuando se descarta más del 10 % de las medidas, la línea inferior indica «Parásitos descartados: xx %».

# 9. Comparar antes y después: la curva A

![Tras «Memorizar A», la curva A (puntos blancos) queda en pantalla; la línea inferior compara graves y presencia.](images/analyseur_ab.jpg){w=482}

Para ayudar a un corresponsal a ajustar su audio:

1. Déjelo hablar unos segundos y haga clic en **Memorizar A**: la curva de voz media queda fijada en **puntos blancos**.
2. Él modifica su ecualizador o su compresor. Haga clic en **↺ Reiniciar** para partir de una medida nueva.
3. La nueva curva azul se superpone a la curva A. La línea inferior da la evolución, por ejemplo «graves −21 dB → −12 dB».

La curva A se ajusta al nivel actual de los medios: el fading cambia el nivel, no la forma. **Borrar A** la quita.

# 10. El informe de escucha

![El informe de escucha se abre en cualquier navegador, con el audio, los veredictos y la imagen del espectro.](images/analyseur_rapport.jpg){w=420}

El botón **🎧 Generar un informe de escucha** descarga un archivo HTML autónomo, por ejemplo «Rapport-ORSAT-14200,000kHz-USB-20261019-0934.html». Se abre en cualquier navegador, sin conexión, y se envía por correo electrónico. Contiene:

- la frecuencia, el modo, la fecha y la hora UTC, y la referencia tonal;
- un **reproductor de audio** con los **últimos 20 segundos** del audio bruto del receptor, normalizado en nivel, y un enlace para descargar ese audio en WAV;
- la tabla de veredictos con sus pilotos;
- la comparación con la curva A, si existe;
- una **imagen del espectro** en el momento del informe.

> [Nota] El archivo pesa alrededor de 1 MB. El fragmento procede del audio bruto: lo que oye el corresponsal no depende de sus ajustes de escucha. El informe en sí está redactado en francés.

# 11. Consejos para medidas fiables

- **Haga zoom en la cascada** sobre la estación: el ancho ocupado, la portadora, la banda opuesta y la vista RF dependen de ello.
- **Abra el filtro de recepción**: para juzgar los graves debe bajar hasta unos 120 Hz; para la presencia, subir hasta unos 2,6 kHz. Un filtro 100–2800 Hz es adecuado.
- **Prefiera una estación con más de 15 dB de relación señal/ruido**. Por debajo, el informe indica «Señal débil: fiabilidad reducida».
- **El fading selectivo** deforma el espectro de un instante a otro: la media sobre 20 s lo atenúa, pero un informe tomado durante un fading fuerte sigue siendo indicativo.
- **Compare lo comparable**: misma referencia tonal, mismo filtro, mismo zoom de cascada.

# 12. Mensajes y solución de problemas

| Mensaje | Significado y remedio |
| Esperando modulación… | Menos de 3 s de voz analizados: deje hablar a la estación. |
| Haga zoom sobre la estación en la cascada… | La cascada es demasiado ancha para medir: haga zoom sobre la estación. |
| no medible: el filtro RX corta… | El filtro de recepción oculta la zona medida: ensánchelo. |
| ocupada por otra estación (QRM) | La banda opuesta contiene otra señal: medida imposible. |
| Señal débil: fiabilidad reducida | Relación señal/ruido inferior a 15 dB. |
| Parásitos descartados: xx % | La banda crepita: el informe se basa en menos voz. |
| Sin fragmento de audio (informe) | El analizador llevaba muy poco tiempo abierto: espere unos segundos. |
