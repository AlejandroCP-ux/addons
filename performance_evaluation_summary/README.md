CORRECCIONES INCLUIDAS EN ESTA VERSIÓN:
- Eliminado uso de ir.values (obsoleto en Odoo >= 13).
- Eliminada la referencia directa a view_id en el action (se usa view_mode/form + target=new).
- Se actualizaron permisos en security/ir.model.access.csv para permitir create/read/write del wizard (requerido para transient models).
- Plantilla QWeb del reporte reescrita para siempre renderizar un HTML completo con un elemento <main>, evitando el error:
  IndexError: list index out of range (body_parent = root.xpath('//main')[0])
- Se sustituyeron los usos incorrectos de 'loop' por 'enumerate' en las iteraciones y se protegió el acceso a índices.
- El wizard ahora valida existencia del XMLID del reporte antes de llamar report_action y lanza UserError claro si falta.

Recomendaciones para instalación y pruebas:
1) Copia el ZIP al directorio de addons o instala desde Interfaz -> Apps -> instalar módulo desde archivo ZIP.
2) Activa modo desarrollador, actualizar lista de módulos e instalar el módulo 'Performance Evaluation Summary'.
3) Probar: Menú 'Resumen de evaluaciones' -> abrir wizard -> seleccionar empleado con subordinados y período -> Imprimir.
4) Revisar logs si ocurren errores; los problemas típicos son: dependencia 'performance_evaluation' no instalada, o plantilla 'performance.evaluation.program' con campos distintos.

Si quieres que:
- el resumen incluya subordinados recursivos (varios niveles),
- se agregue filtro por departamento,
- se genere CSV además del PDF,
- o se añadan columnas extra en el reporte (comentarios, evaluador, fecha),
dímelo y lo preparo.
