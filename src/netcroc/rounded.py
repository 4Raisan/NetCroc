"""Rounded nine-slice ttk surfaces; native widgets retain keyboard/accessibility behavior."""
from PIL import Image,ImageDraw,ImageTk

def install(style,master,palette,owner):
    if not hasattr(owner,'rounded_images'):owner.rounded_images=[]
    def surface(name,fill,outline,radius=6):
        image=Image.new('RGBA',(32,32));draw=ImageDraw.Draw(image)
        draw.rounded_rectangle((1,1,30,30),radius,fill=fill,outline=outline,width=1)
        photo=ImageTk.PhotoImage(image,master=master);owner.rounded_images.append(photo)
        element='NetCroc.'+name
        if element in style.element_names():
            # Elements retain their image object; update pixels without recreating layouts.
            owner.rounded_photos[name].paste(image)
            owner.rounded_images.pop()
        else:
            style.element_create(element,'image',photo,border=8,sticky='nswe')
            owner.rounded_photos[name]=photo
        return element
    if not hasattr(owner,'rounded_photos'):owner.rounded_photos={}
    dark=palette['base'].startswith(('#1','#2'))
    border='#809b8d' if not dark else '#738b80'
    for name,fill in [('normal',palette['button']),('hover',palette['button_active']),('primary',palette['primary']),('selected',palette['segment_selected']),('card',palette['card']),('field',palette['field'])]:
        surface(name,fill,border if name not in ('primary','card') else palette['primary'] if name=='primary' else palette['border'],6)
    for target in ('TButton','SidebarAction.TButton','Nav.TButton','ToolNav.TButton','Primary.TButton','Update.TButton','Copy.TButton'):
        primary=target in ('Primary.TButton','Update.TButton')
        if primary:
            surface('primary_hover',palette['primary_active'],palette['primary_active'],8)
        if target=='Update.TButton':surface('update',palette['primary'],palette['primary'],10)
        normal=owner.rounded_photos['update' if target=='Update.TButton' else 'primary' if primary else 'normal']
        hover=owner.rounded_photos['primary_hover' if primary else 'hover']
        selected=owner.rounded_photos['primary_hover' if primary else 'selected']
        element='NetCroc.primary' if primary else 'NetCroc.normal'
        state_element='NetCroc.state.'+target
        if state_element not in style.element_names():
            style.element_create(state_element,'image',normal,('disabled',owner.rounded_photos['card']),('pressed',selected),('selected',selected),('active',hover),('focus',selected),border=12 if target=='Update.TButton' else 8,sticky='nswe')
        element=state_element
        style.layout(target,[(element,{'sticky':'nswe','children':[('Button.padding',{'sticky':'nswe','children':[('Button.label',{'sticky':'nswe'})]})]})])
    style.layout('Card.TFrame',[('NetCroc.card',{'sticky':'nswe'})])
    style.layout('Quiet.TNotebook',[('NetCroc.card',{'sticky':'nswe','children':[('Notebook.client',{'sticky':'nswe'})]})])
    style.configure('TButton',padding=(10,4))
    style.configure('SidebarAction.TButton',padding=(5,4))
    style.configure('Treeview',borderwidth=0)
    style.configure('TEntry',borderwidth=0)

    def soften(widget):
        import tkinter as tk
        from tkinter import ttk
        if isinstance(widget,(ttk.Treeview,ttk.Combobox,ttk.Entry,tk.Canvas)) and not getattr(widget,'_rounded_bound',False):
            widget._rounded_bound=True
            def shape(event):
                if event.widget is widget:
                    owner.app.window.set_round_region(widget.winfo_id(),event.width,event.height,14)
            widget.bind('<Configure>',shape,add='+')
        for child in widget.winfo_children():soften(child)
    soften(owner.book)

    style.configure('Nav.TButton',padding=(6,1),font=('Segoe UI',9))
    style.configure('ToolNav.TButton',padding=(6,0))

    # Navigation is quiet by default; selection and hover supply the visual cue.
    for target in ('Nav.TButton','ToolNav.TButton'):
        style.layout(target,[('Button.padding',{'sticky':'nswe','children':[('Button.label',{'sticky':'nswe'})]})])
        style.configure(target,background=palette['side'],borderwidth=0,anchor='w')
        style.map(target,background=[('selected',palette['segment_selected']),('active',palette['button_active'])],foreground=[('selected',palette['foreground'])])

    style.configure('Nav.TButton',padding=(8,5))
    style.configure('ToolNav.TButton',padding=(8,4))

    style.configure('Update.TButton',padding=(2,3),font=('Segoe UI',9,'bold'),foreground='#ffffff',anchor='center')
