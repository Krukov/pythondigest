# -*- coding: utf-8 -*-
from datetime import datetime, timedelta

from django.contrib import admin
from django.db import models
from django import forms
from django.core.urlresolvers import reverse
from django.contrib.sites.models import Site
from django.utils.html import escape

from digest.forms import ItemStatusForm
from digest.models import Issue, Section, Item, Resource, AutoImportResource, \
    ParsingRules, Tag, Package, get_start_end_of_week

admin.site.unregister(Site)


def _link_html(obj):
    link = escape(obj.link)
    return u'<a target="_blank" href="%s">%s</a>' % (link, link)


def _external_link(obj):
    lnk = escape(obj.link)
    ret = u'<a target="_blank" href="%s">Ссылка&nbsp;&gt;&gt;&gt;</a>' % lnk
    username = obj.user.username if obj.user else u'Гость'
    ret = u'%s<br>Добавил: %s' % (ret, username)
    return ret


class IssueAdmin(admin.ModelAdmin):

    list_display = (
        'title',
        'news_count',
        'issue_date',
        'frontend_link',
    )

    list_filter = (
        'date_from',
        'date_to',
    )

    exclude = (
        'last_item',
        'version',
    )

    def issue_date(self, obj):
        return u"С %s по %s" % (obj.date_from, obj.date_to)

    issue_date.short_description = u"Период"

    def news_count(self, obj):
        return u"%s" % Item.objects.filter(issue__pk=obj.pk,
                                           status='active').count()

    news_count.short_description = u"Количество новостей"

    def frontend_link(self, obj):
        lnk = reverse('frontend:issue_view', kwargs={'pk': obj.pk})
        return u'<a target="_blank" href="%s">%s</a>' % (lnk, lnk)
    frontend_link.allow_tags = True
    frontend_link.short_description = u"Просмотр"

admin.site.register(Issue, IssueAdmin)


class SectionAdmin(admin.ModelAdmin):
    pass
admin.site.register(Section, SectionAdmin)


class ParsingRulesAdmin(admin.ModelAdmin):
    list_display = (
        'name',
        'is_activated',
        'weight',
        'if_element',
        '_get_if_action',
        'then_element',
        '_get_then_action',
    )

    list_filter = (
        'is_activated',
        'if_element',
        'if_action',
        'then_element',
        'then_action',
    )

    list_editable = (
        'is_activated',
    )

    search_fields = (
        'is_activated',
        'name',
        'if_value',
        'then_value',
    )

    def _get_if_action(self, obj):
        return u"{}: <i>{}</i>".format(obj.get_if_action_display(), obj.if_value)

    _get_if_action.allow_tags = True
    _get_if_action.short_description = u"Условие"

    def _get_then_action(self, obj):
        return u"{}: <i>{}</i>".format(obj.get_then_action_display(), obj.then_value)

    _get_then_action.allow_tags = True
    _get_then_action.short_description = u"Действие"

admin.site.register(ParsingRules, ParsingRulesAdmin)


class TagAdmin(admin.ModelAdmin):
    search_fields = ('name', )

    list_display = (
        'name',
        'news_count',
        'news_count_last_week',
        'news_count_last_month',
    )

    def _get_text(self, active_cnt, all_cnt):
        return "<font color='green'><b>{}</b></font> / " \
               "<font color='gray'>{}</font>".format(active_cnt, all_cnt)

    def news_count(self, obj):
        return self._get_text(
            Item.objects.filter(status='active', tags__name=obj.name).count(),
            Item.objects.filter(tags__name=obj.name).count())

    def news_count_last_week(self, obj):
        now = datetime.now().date()
        week_before = datetime.now().date() - timedelta(weeks=1)
        return self._get_text(
            Item.objects.filter(status='active',
                                tags__name=obj.name,
                                created_at__range=(week_before, now)
                                ).count(),
            Item.objects.filter(tags__name=obj.name,
                                created_at__range=(week_before, now)
                                ).count(),
        )

    def news_count_last_month(self, obj):
        now = datetime.now().date()
        week_before = datetime.now().date() - timedelta(weeks=4)
        return self._get_text(
            Item.objects.filter(status='active',
                                tags__name=obj.name,
                                created_at__range=(week_before, now)
                                ).count(),
            Item.objects.filter(tags__name=obj.name,
                                created_at__range=(week_before, now)
                                ).count(),
        )

    news_count.short_description = u"Активных/всего новостей"
    news_count.allow_tags = True

    news_count_last_week.short_description = u"Активных/всего за неделю"
    news_count_last_week.allow_tags = True

    news_count_last_month.short_description = u"Активных/всего за 4 недели"
    news_count_last_month.allow_tags = True


admin.site.register(Tag, TagAdmin)


class ItemAdmin(admin.ModelAdmin):

    form = ItemStatusForm
    fields = (
        'section',
        'title',
        'is_editors_choice',
        'description',
        'link',
        'status',
        'language',
        'tags',
    )
    filter_horizontal = ('tags',)
    list_filter = (
        'status',
        'issue',
        'section',
        'is_editors_choice',
        'user',
        'related_to_date',
        'resource',
    )
    search_fields = ('title', 'description', 'link', 'resource__title')
    list_display = (
        'title',
        'status',
        'external_link',
        'related_to_date',
        'is_editors_choice',
    )

    list_editable = ('is_editors_choice',)
    exclude = ('modified_at',),
    radio_fields = {
        'language': admin.HORIZONTAL,
        'status': admin.HORIZONTAL,
    }

    external_link = lambda s, obj: _external_link(obj)
    external_link.allow_tags = True
    external_link.short_description = u"Ссылка"

    def save_model(self, request, obj, form, change):
        prev_status = False
        if not obj.pk:
            obj.user = request.user
            if not obj.issue:
                la = lna = False
                qs = Issue.objects
                try:
                    # последний активный
                    la = qs.filter(status='active').order_by('-pk')[0:1].get()
                    # последний неактивный
                    lna = qs.filter(pk__gt=la.pk).order_by('pk')[0:1].get()
                except Issue.DoesNotExist:
                    pass

                if la or lna:
                    obj.issue = lna or la
        else:
            old_obj = Item.objects.get(pk=obj.pk)
            prev_status = old_obj.status

        # Обновление времени модификации при смене статуса на активный
        new_status = form.cleaned_data.get('status')
        if not prev_status == 'active' and new_status == 'active':
            obj.modified_at = datetime.now()

        super(ItemAdmin, self).save_model(request, obj, form, change)
admin.site.register(Item, ItemAdmin)


class ResourceAdmin(admin.ModelAdmin):
    list_display = ('title', 'link_html')

    link_html = lambda s, obj: _link_html(obj)
    link_html.allow_tags = True
    link_html.short_description = u"Ссылка"
admin.site.register(Resource, ResourceAdmin)


class AutoImportResourceAdmin(admin.ModelAdmin):
    list_display = ('name', 'link_html', 'type_res', 'resource', 'incl', 'excl', 'in_edit', 'language')
    formfield_overrides = {
        models.TextField: {'widget': forms.Textarea(attrs={'cols': 45, 'rows': 1})},
    }

    link_html = lambda s, obj: _link_html(obj)
    link_html.allow_tags = True
    link_html.short_description = u"Ссылка"


admin.site.register(AutoImportResource, AutoImportResourceAdmin)


class PackageAdmin(admin.ModelAdmin):
    pass
admin.site.register(Package, PackageAdmin)


class ItemModerator(Item):
    class Meta:
        proxy = True
        verbose_name_plural = 'Новости (эксперимент)'


class ItemModeratorAdmin(admin.ModelAdmin):
    form = ItemStatusForm
    fields = (
        'section',
        'title',
        'is_editors_choice',
        'description',
        'external_link_edit',
        'status',
        'language',
    )

    readonly_fields = (
        'external_link_edit',
    )

    filter_horizontal = ('tags',)
    list_filter = (
        'status',
        'issue',
        'section',
        'is_editors_choice',
        'user',
        'related_to_date',
        'resource',
    )
    search_fields = ('title', 'description', 'link', 'resource__title')
    list_display = (
        'title',
        'status',
        'external_link',
        'related_to_date',
        'is_editors_choice',
    )

    list_editable = ('is_editors_choice',)
    exclude = ('modified_at',),
    radio_fields = {
        'language': admin.HORIZONTAL,
        'status': admin.HORIZONTAL,
    }

    actions = ['make_moderated']

    def make_moderated(self, request, queryset):
        try:
            item = queryset.latest('pk')
            _start_week, _end_week = get_start_end_of_week(item.related_to_date)
            issue = Issue.objects.filter(date_from=_start_week, date_to=_end_week)
            assert len(issue) == 1
            issue.update(last_item=item.pk)
        except Exception:
            raise

    make_moderated.short_description = 'Отмодерирован'

    def get_queryset(self, request):

        # todo
        # потом переписать на логику:
        # ищем связку выпусков
        # неактивный, а перед ним активный
        # если такая есть, то публикуем новости у которых время в периоде
        # неактивного
        # если нету, то  отдаем все

        # сейчас логика такая:
        # берем выпуск за текущую неделю
        # если перед ним активный, то показываем новость за текущую неделю
        # если нет, то все новости показываем
        try:
            start_week, end_week = get_start_end_of_week(datetime.now().date())
            before_issue = Issue.objects.filter(date_to=end_week - timedelta(days=7))
            assert len(before_issue) == 1
            if before_issue[0].status == 'active':
                current_issue = Issue.objects.filter(date_to=end_week, date_from=start_week)
                assert len(current_issue) == 1
                current_issue = current_issue[0]
            else:
                current_issue = before_issue[0]

            result = self.model.objects.filter(
                status__in=['pending', 'moderated', 'active', 'autoimport'],
                related_to_date__range=[current_issue.date_from, current_issue.date_to]
            )

            if current_issue.last_item is not None:
                result = result.filter(
                    pk__gt=current_issue.last_item,
                )
        except AssertionError:
            result = super(ItemModeratorAdmin, self).get_queryset(request)
        return result

    external_link = lambda s, obj: _external_link(obj)
    external_link.allow_tags = True
    external_link.short_description = u"Ссылка"

    external_link_edit = lambda s, obj: _link_html(obj)
    external_link_edit.allow_tags = True
    external_link_edit.short_description = u"Ссылка"

    def save_model(self, request, obj, form, change):
        prev_status = False
        if not obj.pk:
            obj.user = request.user
            if not obj.issue:
                la = lna = False
                qs = Issue.objects
                try:
                    # последний активный
                    la = qs.filter(status='active').order_by('-pk')[0:1].get()
                    # последний неактивный
                    lna = qs.filter(pk__gt=la.pk).order_by('pk')[0:1].get()
                except Issue.DoesNotExist:
                    pass

                if la or lna:
                    obj.issue = lna or la
        else:
            old_obj = Item.objects.get(pk=obj.pk)
            prev_status = old_obj.status

        # Обновление времени модификации при смене статуса на активный
        new_status = form.cleaned_data.get('status')
        if not prev_status == 'active' and new_status == 'active':
            obj.modified_at = datetime.now()

        super(ItemModeratorAdmin, self).save_model(request, obj, form, change)


admin.site.register(ItemModerator, ItemModeratorAdmin)
