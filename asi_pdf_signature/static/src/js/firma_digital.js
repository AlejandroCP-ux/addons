odoo.define("firma_digital.firma_digital", (require) => {
  var core = require("web.core")
  var FormView = require("web.FormView")
  var FormController = require("web.FormController")
  var FormRenderer = require("web.FormRenderer") // Declare the FormRenderer variable
  var $ = require("jquery") // Declare the $ variable
  var _t = core._t

  // Extender el renderizador del formulario para añadir funcionalidades específicas
  FormRenderer.include({
    _renderWidget: function (widget, node) {
      var $el = this._super.apply(this, arguments)

      // Añadir código personalizado para la vista del formulario de firma si es necesario
      if (this.state.model === "firma.documento.wizard") {
        // Código específico para la vista de firma de documentos
      }

      return $el
    },
  })

  // Extender el controlador del formulario para añadir funcionalidades específicas
  FormController.include({
    _onButtonClicked: function (event) {
      // Si se ha completado la acción de firma, verificar si debe descargarse automáticamente
      if (this.modelName === "firma.documento.wizard" && event.data.attrs.name === "action_firmar_documentos") {
        return this._super.apply(this, arguments).then((action) => {
          // El resto se maneja en el wizard
          return action
        })
      }

      // Si se ha completado la acción de firma, verificar si debe descargarse automáticamente
      if (this.modelName === "firma.documento.wizard" && event.data.attrs.name === "action_firmar_documento") {
        // El resto se maneja normalmente
        return this._super.apply(this, arguments).then((action) => {
          // Verificar si debemos descargar el PDF automáticamente
          if (action && this.renderer.state.data.estado === "firmado" && this.renderer.state.context.descargar_pdf) {
            this._rpc({
              model: "firma.documento.wizard",
              method: "action_descargar_pdf",
              args: [this.renderer.state.res_id],
            }).then((result) => {
              if (result && result.type === "ir.actions.act_url") {
                window.location = result.url
              }
            })
          }
          return action
        })
      }

      return this._super.apply(this, arguments)
    },
  })
})
