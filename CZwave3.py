import csv
import os
import math
import numpy as np
import qutip as qt
from scipy import constants
from scipy import interpolate
from scipy import integrate
import sympy as sym

import matplotlib.pyplot as plt
import sys
from systemConst import Tunabletransmon,QQ
from tqdm import tqdm

pi = np.pi
e = constants.e # [C]
h = constants.h # [m^2 kg/s]
hbar = constants.hbar
iDir = os.path.abspath(os.path.dirname(__file__))
opts = qt.solver.Options(nsteps=10000)

class CZpulse():
    def __init__(self,Q1,Q2,J,lambda2=0.10,the_f=0.85,steps=1,tg=None): #Jは/2piのものを入れる
        self.Nq1=Q1.Nq
        self.Nq2=Q2.Nq
        if self.Nq1!=self.Nq2:
            print("error")
        else:
            self.Nq=self.Nq1
        self.fq1=Q1.f01
        self.anh1=Q1.anh
        self.fq2=Q2.f01
        self.anh2=Q2.anh
        self.qFreq20=self.fq1+abs(self.anh2)
        self.J=J
        self.lambda2=lambda2
        self.the_f=the_f
        self.steps=steps
        self.delta=self.fq2-self.fq1-abs(self.anh2)
        self.the_i=math.atan(2*np.sqrt(2)*self.J/self.delta)
        self.lambdas=[self.the_i,(self.the_f*(pi/2)-self.the_i)/2,self.lambda2]
        if tg==None:
            self.tg=round(1/(2*np.sqrt(2)*J),1)
        else:
            self.tg=tg
        self.t_list=np.linspace(0,self.tg,int(self.tg*self.steps))
    
    def squarepulse(self,t_ini,t_ramp,PLOT=False):
        Tg = self.tg
        t_list = np.linspace(0,Tg,int(Tg*self.steps))
        shape = []
        
        for t in t_list:
            if t < t_ini:
                a = self.fq2
            elif t <= t_ini + t_ramp:
                a = self.fq2 - (self.fq2-self.qFreq20) / t_ramp*(t-t_ini)
            elif t > Tg - (t_ini):
                a = self.fq2
            elif t >= Tg - (t_ramp+t_ini):
                a = self.fq2 - (self.fq2-self.qFreq20)  / t_ramp*(Tg-(t+t_ini))
            else:
                a = self.qFreq20
            shape.append(round(a,5))
        
        if PLOT==True:
            plt.figure()
            plt.plot(t_list,shape)
            plt.ylim([self.qFreq20-0.1,self.fq2+0.1])
            plt.hlines(self.qFreq20,0,Tg,linestyle='dashed')
            plt.xlabel('t[ns]')
            plt.ylabel('frequency[GHz]')
            plt.show()
            
        return t_list,shape
    
    
    def co_optim(self,taug,tg=0):

        if tg==0:
            tg=self.tg
        tau_list=np.linspace(0,taug,int(tg*self.steps))
        
        def theta_tau(t): #θを制御するスレピアン関数
            theta=self.lambdas[0]
            for i in range(1,len(self.lambdas)):
                theta=theta+self.lambdas[i]*(1-np.cos(2*pi*t*i/taug))
            return theta
    
        def sintheta_tau(t):
            theta=theta_tau(t)
            sintheta=np.sin(theta)
            return sintheta

        t_tau=[]
        for i in range(len(tau_list)):
            t_tau.append(integrate.quad(sintheta_tau,0,tau_list[i])[0])
        return(t_tau,theta_tau(tau_list),taug/t_tau[-1])
    
    def phasechange(self,tg=0):
        if tg!=0:
            self.tg=tg
        t_list=np.linspace(0,self.tg,int(self.tg*self.steps))
        theta_list=self.co_optim(taug=self.tg,tg=tg)[1] #静止座標系のθ(0)~θ(tg)
        f1=interpolate.interp1d(t_list,theta_list,fill_value="extrapolate") #θ(t) calculated
        return t_list,f1(t_list)
    
    def adiabaticpulse(self,tg=0,PLOT=False): #unipolar adiabatic pulse
        if tg==0:
            tg=self.tg
        theta_list=self.co_optim(taug=tg,tg=tg)[1]
        t_list=np.linspace(0,tg,len(theta_list))
        f1=interpolate.interp1d(t_list,theta_list,fill_value="extrapolate")
        y1=f1(t_list)
        freqchange = 2*np.sqrt(2)*self.J/np.tan(y1)+self.qFreq20

        if PLOT==True:
            plt.figure()
            plt.plot(t_list,freqchange)
            plt.ylim([self.qFreq20-0.1,self.fq2+0.1])
            plt.hlines(self.qFreq20,0,tg,linestyle='dashed')
            plt.xlabel('t[ns]')
            plt.ylabel('frequency[GHz]')
            plt.show()

        return t_list,freqchange

    def adiabaticcurrent(self,M=1,offset=0,PLOT=False):
        t_list,freqs=self.adiabaticpulse()
        _current=np.arccos(((freqs-abs(self.anh2))**2/(self.fq2-abs(self.anh2))**2))/pi
        current=(_current+offset)/M

        if PLOT==True:
            plt.figure()
            plt.plot(t_list,current)
            plt.title('Current on Q2(Unipolar)')
            plt.xlabel('t[ns]')
            plt.ylabel('Iq2[a.u.]')
            plt.show()

        return t_list,current

    def netzeropulse(self,PLOT=False):
        tghalf=self.tg/2
        firsthalf_freq=self.adiabaticpulse(tghalf)[1]
        secondhalf_freq=self.adiabaticpulse(tghalf)[1]
        t_list=np.linspace(0,self.tg,len(firsthalf_freq)+len(secondhalf_freq))
        #firsthalf_freq.extend(secondhalf_freq)
        netzerofreq=np.append(firsthalf_freq,secondhalf_freq)

        if PLOT==True:
            plt.figure()
            plt.plot(t_list,netzerofreq)
            plt.ylim([self.qFreq20-0.1,self.fq2+0.1])
            plt.hlines(self.qFreq20,0,self.tg,linestyle='dashed')
            plt.xlabel('t[ns]')
            plt.ylabel('frequency[GHz]')
            plt.show()
        return t_list,netzerofreq
    
    def netzerocurrent(self,M=1,offset=0,PLOT=False):
        t_list,freqs=self.netzeropulse()
        _current=np.zeros(len(freqs))

        for i,freq in enumerate(freqs):
            if i<=len(freqs)/2:
                _current[i]=np.arccos(((freq-abs(self.anh2))**2/(self.fq2-abs(self.anh2))**2))/pi #[phi_0]
            else:
                _current[i]=-np.arccos(((freq-abs(self.anh2))**2/(self.fq2-abs(self.anh2))**2))/pi #[phi_0]
        current=(_current+offset)/M #Mの単位は

        if PLOT==True:
            plt.figure()
            plt.plot(t_list,current)
            plt.title('Current on Q2(Net-Zero)')
            plt.xlabel('t[ns]')
            plt.ylabel('Iq2[a.u.]')
            plt.show()

        return t_list,current
    
    def current_to_flux(self,t_list,current1,current2=0,Ioffset=0,m=1,mleak=0,PLOT=False,Qlabel='2'):
        flux = m*(current1-Ioffset)+mleak*current2 #mの単位は[Φ0/mA]
        if PLOT==True:
            plt.figure()
            plt.plot(t_list,flux)
            plt.title('Flux on Q2(Net-Zero)')
            plt.xlabel('t[ns]')
            plt.ylabel('Iq{}[a.u.]'.format(Qlabel))
            plt.show()

        return t_list,flux
        
    def cancellationcurrent(self,m11,m12,m21,m22,Ioffset1,Ioffset2,pulsetype='Adiabatic',PLOT=False): #バイアスライン2から1のm: m12, バイアスライン1から2のm:m21
        canc_coeff = m22-(m12*m21)/m11
        if pulsetype=='Adiabatic':
            t_list,adiabaticcurrent = self.adiabaticcurrent()
            I_tune = adiabaticcurrent/canc_coeff + (m21*Ioffset1-m22*Ioffset2)/canc_coeff
            I_cancel = -m12/m11*I_tune+Ioffset1
        elif pulsetype=='Net-Zero':
            t_list,netzerocurrent = self.netzerocurrent()
            I_tune = netzerocurrent/canc_coeff + (m21*Ioffset1-m22*Ioffset2)/canc_coeff
            I_cancel = -m12/m11*I_tune+Ioffset1
        
        pulseheight = abs(max(I_tune)-min(I_tune))/2

        if PLOT is True:
            fig = plt.figure()
            ax1 = fig.add_subplot(111)
            ax1.plot(t_list,I_tune,label='I_tune',color='blue')
            ax1.set_ylim([min(I_tune)-pulseheight*0.25,max(I_tune)+pulseheight*0.25])

            ax2 = ax1.twinx()
            ax2.plot(t_list,I_cancel,label='I_cancel',color='r')
            ax2.set_ylim([min(I_tune)-pulseheight*0.25,max(I_tune)+pulseheight*0.25])

            h1, l1 = ax1.get_legend_handles_labels()
            h2, l2 = ax2.get_legend_handles_labels()
            ax1.legend(h1+h2, l1+l2, loc='lower right')

            ax1.set_xlabel('t')
            ax1.set_ylabel('Tune pulse[mA]')
            ax1.grid(True)
            ax2.set_ylabel('Cancel pulse[mA]')
            plt.show()

        return t_list, [I_tune,I_cancel]

    def flux_to_Qfreq(self,phi,offset=0,Qlabel='1'):
        return (self.fq2-abs(self.anh2))*np.sqrt(np.cos((phi+offset)*pi))+abs(self.anh2)
    
    def current_to_freq(self,offset=0,M=1,m11=1,m12=0,m21=0,m22=1,pulsetype='Adiabatic',Ioffset1=0,Ioffset2=0,PLOT=False):
        if pulsetype=='Adiabatic':
            t_list = self.adiabaticcurrent(M=M,offset=offset)[0]
            pulse = (self.fq2-abs(self.anh2))*np.sqrt(abs(np.cos(self.adiabaticcurrent(M=M,offset=offset)[1]*pi)))+abs(self.anh2)
            return t_list,pulse
        elif pulsetype=='Net-Zero':
            t_list = self.netzerocurrent(M=M,offset=offset)[0]
            pulse = (self.fq2-abs(self.anh2))*np.sqrt(abs(np.cos(self.netzerocurrent(M=M,offset=offset)[1]*pi)))+abs(self.anh2)
            return t_list,pulse
        elif pulsetype =='Cancellaton':
            canc = self.cancellationcurrent(m11,m12,m21,m22,Ioffset1,Ioffset2,PLOT=False)
            t_list = canc[0]
            pulse_tune = (self.fq2-abs(self.anh2))*np.sqrt(abs(np.cos(canc[1][0])))+abs(self.anh2)
            pulse_canc = (self.fq1-abs(self.anh1))*np.sqrt(abs(np.cos(canc[1][1])))+abs(self.anh1)
            return t_list,[pulse_tune,pulse_canc]
        
        if PLOT==True:
            plt.figure()
            plt.plot(t_list,pulse)
            #plt.ylim([self.qFreq20-0.1,self.fq2+0.1])
            plt.hlines(self.qFreq20,0,self.tg,linestyle='dashed')
            plt.title(pulsetype+' pulse-{:.1f}ns'.format(self.tg))
            plt.xlabel('t[ns]')
            plt.ylabel('frequency[GHz]')
            plt.show()

        

    def inversefiltered_pulse(self,pulse,loadpath=None,PLOT=False,savepath=None): #Zhouさんのメソッドを用いて補正していく予定
        if loadpath is None:
            self.FIRfilter=np.load('C:/Sota_Ino/Tsai_Lab/fir_coe.npy')
        else:
            self.FIRfilter=np.load(loadpath)
        
        fs=len(pulse)
        t = np.arange(0,fs)
        print(len(t),len(pulse))
        d = np.zeros(fs)
        b = self.FIRfilter
        for i in range(fs):
            d[i] = 0
            for j in range(len(b)):
                if(i-j)>=0:
                    d[i] += b[j]*pulse[i-j]
        
        if PLOT is True:
            plt.figure()
            plt.plot(t,pulse)
            plt.plot(t,d)
            plt.show()
            if savepath is not None:
                plt.savefig(savepath)
            else:
                pass
        
        Filteredcurrent=d

        return Filteredcurrent

    
    

if __name__=='__main__':
    #Hamiltonian Component
    Ej1 = 17
    Ej2 = 22
    Ec1 = 0.27
    Ec2 = 0.27
    g=0.015 #/2pi

    Q1=Tunabletransmon(EC=Ec1, EJmax=Ej1)
    Q2=Tunabletransmon(EC=Ec2, EJmax=Ej2)
    pulsesystem=CZpulse(Q1,Q2,g,the_f=0.88,lambda2=0.13,tg=48)
    print("the_i={:.2f}".format(pulsesystem.the_i))
    print("Tg={:.1f}".format(pulsesystem.tg))
    print("fq1:{:.2f}".format(Q1.f01))
    print("fq2:{:.2f}".format(Q2.f01))

    x0,y0=pulsesystem.phasechange()
    x1,y1=pulsesystem.adiabaticpulse()
    print(len(y1))
    print(type(fn.slepian_like),type(y1))
    x2,y2=pulsesystem.netzeropulse()
    print(len(y2))
    x3,y3=pulsesystem.adiabaticcurrent()
    x4,y4=pulsesystem.netzerocurrent()

    """
    fig,axes=plt.subplots(nrows=2,ncols=2,figsize=(10,8))
    plt.subplots_adjust(hspace=0.3)
    ax1=axes[0,0]
    ax2=axes[0,1]
    ax3=axes[1,0]
    ax4=axes[1,1]

    ax1.set_title('Phase θ')
    ax1.plot(x0,y0)
    ax1.set_xlabel('t')
    ax1.set_ylabel('θ(t)')
    ax1.grid(True)

    ax2.set_title('Freq')
    ax2.hlines(2*pi*pulsesystem.fq2,0,80,color='black',linestyle='dashed')
    ax2.plot(x1,y1)
    ax2.plot(x2,y2)
    ax2.set_xlabel('t')
    ax2.set_ylabel('ω(t)')
    ax2.grid(True)

    ax3.set_title('Current')
    ax3.plot(x3,y3)
    ax3.plot(x4,y4)
    ax3.set_xlabel('t')
    ax3.set_ylabel('I(t)')
    ax3.grid(True)

    ax4.axis('off')
    plt.savefig(iDir+'/Figure_of_adia.png')

    x0,y0=pulsesystem.squarepulse(1,2)
    x1,y1=pulsesystem.adiabaticcurrent()
    x2,y2=pulsesystem.netzerocurrent()
    """
    
    plt.rcParams["font.size"]=18
    fig,axes=plt.subplots(nrows=3,ncols=1,figsize=(10,15))
    plt.subplots_adjust(hspace=0.5)

    ax1=axes[0]
    ax2=axes[1]
    ax3=axes[2]

    ax1.set_title('SQpulse')
    ax1.plot(x0,y0,linewidth=3.0)
    #ax1.set_ylim(-0.1,0.7)
    ax1.set_xlabel('t[ns]')
    ax1.set_ylabel('I(t)')
    ax1.grid(True)

    ax2.set_title('Adiabatic Pulse')
    #ax2.hlines(pulsesystem.fq2,0,pulsesystem.tg,color='black',linestyle='dashed')
    ax2.plot(x1,y1,linewidth=3.0)
    ax2.set_xlabel('t[ns]')
    ax2.set_ylabel('fq(GHz)')
    ax2.grid(True)

    ax3.set_title('Net-Zero Pulse')
    #ax3.plot(x2,y2,linewidth=3.0)
    ax3.set_xlabel('t[ns]')
    ax3.set_ylabel('I(t)')
    ax3.grid(True)

    plt.savefig(iDir+'/Figure_of_adia.png')