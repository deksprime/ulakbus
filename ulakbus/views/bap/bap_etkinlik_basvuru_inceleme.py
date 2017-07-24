# -*-  coding: utf-8 -*-
# Copyright (C) 2015 ZetaOps Inc.
#
# This file is licensed under the GNU General Public License v3
# (GPLv3).  See LICENSE.txt for details.
from ulakbus.models import AbstractRole
from ulakbus.models import BAPEtkinlikButcePlani
from ulakbus.models import BAPEtkinlikProje
from ulakbus.models import Role
from ulakbus.models import User
from zengine.forms import JsonForm, fields
from zengine.models import BPMNWorkflow
from zengine.models import TaskInvitation
from zengine.models import WFInstance
from zengine.views.crud import CrudView
from zengine.lib.translation import gettext as _, gettext_lazy as __
from pyoko import ListNode
from datetime import datetime, timedelta


class EtkinlikBasvuruInceleForm(JsonForm):
    class Butce(ListNode):
        talep_turu = fields.Integer(__(u"Talep Türü"), required=True,
                               choices='bap_bilimseL_etkinlik_butce_talep_turleri')
        istenen_tutar = fields.Float(__(u"Talep Edilen Tutar"), required=True)


class EtkinlikBasvuruInceleme(CrudView):
    class Meta:
        model = 'BAPEtkinlikProje'

    def __init__(self, current=None):
        super(EtkinlikBasvuruInceleme, self).__init__(current)
        key = self.current.task_data['etkinlik_basvuru_id'] = self.input.get(
            'object_id', False) or self.current.task_data.get('etkinlik_basvuru_id', False)
        self.object = BAPEtkinlikProje.objects.get(key)

    def incele(self):
        key = self.current.task_data['etkinlik_basvuru_id']
        self.show()
        form = EtkinlikBasvuruInceleForm(title="asd")
        form.help_text = _(
            u"Bu projeyi daha sonra etkinlik listele iş akışından ulaşarak inceleyebilirsiniz.")
        form.reddet = fields.Button(_(u"Reddet"), cmd='red')
        form.daha_sonra_incele = fields.Button(_(u"Daha Sonra İncele"), cmd='daha_sonra_incele')
        form.reddet = fields.Button(_(u"Reddet"), cmd='red')
        form.komisyon = fields.Button(_(u"Komisyon Başkanına Gönder"), cmd='komisyon')
        butceler = BAPEtkinlikButcePlani.objects.filter(ilgili_proje_id=key)
        for butce in butceler:
            form.Butce(talep_turu=butce.talep_turu, istenen_tutar=butce.istenen_tutar)
        self.form_out(form)

    def reddet_ve_bildirim_gonder(self):
        """
        Etkinlik başvurusunu yapan öğretim üyesine, başvurunun koordinasyon birimi tarafından
        reddedildiği bildiriminin gönderildiği adımdır.
        """
        role = Role.objects.filter(user=self.object.basvuru_yapan.personel.user)[0]
        sistem_user = User.objects.get(username='sistem_bilgilendirme')
        role.send_notification(title=_(u"Bilimsel Etkinlik Projesi Başvurusu"),
                               message=_(u"%s başlıklı bilimsel etkinlik projesi başvurunuz "
                                         u"koordinasyon birimi tarafondan reddedilmiştir." %
                                         self.object.bildiri_basligi),
                               typ=1,
                               sender=sistem_user
                               )
        self.current.output['cmd'] = 'reload'

    def gorev_basligi_ekle(self):
        # self.current.task_data['INVITATION_TITLE'] = title
        pass

    def incele_kb(self):
        """
        Komisyon başkanının başvuruyu incelediği adımdır.
        """
        key = self.current.task_data['etkinlik_basvuru_id']
        form = EtkinlikBasvuruInceleForm(title="asd")
        form.daha_sonra_incele = fields.Button(_(u"Daha Sonra İncele"), cmd='daha_sonra_devam_et')
        form.reddet = fields.Button(_(u"Reddet"), cmd='red')
        form.komisyon = fields.Button(_(u"Komisyon Üyesi Ata"), cmd='komisyon_uyesi_ata')
        butceler = BAPEtkinlikButcePlani.objects.filter(ilgili_proje_id=key)
        for butce in butceler:
            form.Butce(talep_turu=butce.talep_turu, istenen_tutar=butce.istenen_tutar)
        self.form_out(form)

    def daha_sonra_devam_et(self):
        self.current.output['cmd'] = 'reload'

    def komisyon_uyesi_ata(self):
        form = JsonForm(title=_(u"Komisyon Üyesi Seç"))
        roller = Role.objects.filter(abstract_role=AbstractRole.objects.get(
            name='Bilimsel Arastirma Projesi Komisyon Uyesi'))
        choices = [(rol.key, rol.user.personel.__unicode__()) for rol in roller]
        form.komisyon_uye = fields.String(_(u"Komisyon Üyesi"), required=True, choices=choices)
        form.tamam = fields.Button(_(u"Tamam"))

    def komisyon_uyesine_davet_gonder(self):
        etkinlik_key = self.current.task_data['etkinlik_basvuru_id']
        rol_key = self.input['komisyon_uye']
        role = Role.objects.get(rol_key)
        wf = BPMNWorkflow.objects.get(name='bap_etkinlik_basvuru_degerlendir')
        today = datetime.today()
        wfi = WFInstance(
            wf=wf,
            current_actor=role,
            task=None,
            name=wf.name,
            wf_object=etkinlik_key
        )
        wfi.data = dict()
        wfi.data['flow'] = None
        wfi.data['etkinlik_basvuru_id'] = etkinlik_key
        wfi.pool = {}
        wfi.blocking_save()
        inv = TaskInvitation(
            instance=wfi,
            role=role,
            wf_name=wfi.wf.name,
            progress=30,
            start_date=today,
            finish_date=today + timedelta(15)
        )
        inv.title = wfi.wf.title
        inv.save()
